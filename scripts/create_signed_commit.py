#!/usr/bin/env python3
"""Create a signed commit on a remote branch through the GitHub GraphQL API.

A commit built by local ``git commit`` is never signed, whatever token pushes
it, so every mirror sync landed in the distribution repository as Unverified.
GitHub signs the commits it constructs itself, so this helper hands the staged
change set to the ``createCommitOnBranch`` mutation and lets GitHub author the
commit object. No key material is involved anywhere.

The change set is read from the git index, so the resulting tree is identical
to the one ``git add -A && git commit`` would have produced: the same paths,
the same blob bytes, and the same removals.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Iterable, Mapping, Sequence
import urllib.error
import urllib.request


GITHUB_API = "https://api.github.com"
GRAPHQL_ENDPOINT = f"{GITHUB_API}/graphql"
USER_AGENT = "endor-labs-agent-kit-sync"

# GitHub rejects an oversized ``createCommitOnBranch`` request outright. The cap
# is not documented, and reports of the server-side figure vary, so this helper
# refuses well below every reported value and fails the job rather than letting
# the request be rejected halfway through a release. Splitting a sync across
# several commits is deliberately not implemented: a mirror holding a subset of
# the catalog is worse than a mirror that was not updated at all.
DEFAULT_MAX_PAYLOAD_BYTES = 35 * 1024 * 1024

COMMIT_MUTATION = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) {
    commit {
      oid
      url
    }
  }
}
"""

# ``(method, url, headers, body) -> (status, response_bytes)``.
Transport = Callable[[str, str, Mapping[str, str], bytes | None], "tuple[int, bytes]"]


class CommitError(RuntimeError):
    """A failure that must stop the publish job."""


class PayloadTooLarge(CommitError):
    """The change set is too large to commit in one API request."""


class FileChanges:
    """The additions and deletions of a single commit."""

    def __init__(
        self,
        additions: Sequence[tuple[str, bytes]] = (),
        deletions: Sequence[str] = (),
    ) -> None:
        self.additions = list(additions)
        self.deletions = list(deletions)

    def __bool__(self) -> bool:
        return bool(self.additions or self.deletions)

    def as_input(self) -> dict[str, list[dict[str, str]]]:
        """Render the change set as a GraphQL ``FileChanges`` input value."""

        return {
            "additions": [
                {"path": path, "contents": base64.b64encode(blob).decode("ascii")}
                for path, blob in self.additions
            ],
            "deletions": [{"path": path} for path in self.deletions],
        }

    def summary(self) -> str:
        return f"{len(self.additions)} added or updated, {len(self.deletions)} deleted"


def _git_bytes(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def ensure_commit_available(repo: Path, remote: str, oid: str) -> None:
    """Fetch ``oid`` when the shallow checkout does not already hold it."""

    try:
        _git_bytes(repo, "cat-file", "-e", f"{oid}^{{commit}}")
        return
    except subprocess.CalledProcessError:
        pass
    try:
        _git_bytes(repo, "fetch", "--no-tags", "--depth=1", remote, oid)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace").strip()
        raise CommitError(f"could not fetch {oid} from {remote}: {stderr}") from exc


REGULAR_FILE_MODE = "100644"
ABSENT_MODE = "000000"


def unexpressible_modes(
    changes: Iterable[tuple[str, str, str]],
) -> list[str]:
    """Return the paths whose file mode the commit API cannot express.

    ``FileAddition`` carries a path and contents but no mode. GitHub keeps the
    mode a path already has in the parent tree and creates anything new as a
    regular file, so a newly added executable hook would land in the mirror
    without its executable bit and nothing downstream would notice. Only two
    shapes survive the round trip unchanged: a new path that is a regular
    file, and an existing path whose mode does not change.
    """

    offenders = []
    for path, source_mode, target_mode in changes:
        if source_mode == ABSENT_MODE:
            if target_mode != REGULAR_FILE_MODE:
                offenders.append(f"{path} (new file needs mode {target_mode})")
        elif source_mode != target_mode:
            offenders.append(f"{path} ({source_mode} becomes {target_mode})")
    return offenders


def staged_file_changes(repo: Path, parent: str) -> FileChanges:
    """Diff the git index against ``parent`` and read the resulting blobs.

    Reading content out of the index rather than the working tree keeps the
    bytes byte-exact with what ``git commit`` would have stored, including for
    binary assets and for any path a clean filter rewrites on staging.
    """

    raw = _git_bytes(repo, "diff", "--cached", "--raw", "--no-renames", "-z", parent)
    fields = [field for field in raw.split(b"\0") if field]
    if len(fields) % 2:
        raise CommitError("could not parse the staged change set from git")

    additions: list[tuple[str, bytes]] = []
    deletions: list[str] = []
    modes: list[tuple[str, str, str]] = []
    for meta_field, path_field in zip(fields[::2], fields[1::2]):
        # ":<source mode> <target mode> <source oid> <target oid> <status>"
        parts = meta_field.decode("utf-8").lstrip(":").split()
        if len(parts) != 5:
            raise CommitError(f"could not parse the staged change {meta_field!r}")
        source_mode, target_mode, _source_oid, target_oid, status = parts
        path = path_field.decode("utf-8")
        if status[:1] == "D":
            deletions.append(path)
        elif status[:1] in {"A", "M", "T"}:
            modes.append((path, source_mode, target_mode))
            additions.append((path, _git_bytes(repo, "cat-file", "blob", target_oid)))
        else:
            raise CommitError(f"unsupported staged change status {status!r} for {path}")

    offenders = unexpressible_modes(modes)
    if offenders:
        raise CommitError(
            "the commit API cannot set a file mode, so this sync would change "
            "the mirror's modes silently: "
            + ", ".join(sorted(offenders))
            + ". GitHub keeps whatever mode a path already has, so land each "
            "path in the mirror once at the mode it needs and later syncs will "
            "preserve it."
        )
    return FileChanges(additions, deletions)


def build_commit_input(
    *,
    repository: str,
    branch: str,
    message: str,
    expected_head_oid: str,
    changes: FileChanges,
) -> dict[str, object]:
    return {
        "branch": {
            "repositoryNameWithOwner": repository,
            "branchName": branch,
        },
        "message": {"headline": message},
        "expectedHeadOid": expected_head_oid,
        "fileChanges": changes.as_input(),
    }


def encode_request(query: str, variables: Mapping[str, object]) -> bytes:
    return json.dumps({"query": query, "variables": variables}).encode("utf-8")


def check_payload_size(body: bytes, limit: int) -> None:
    if len(body) > limit:
        raise PayloadTooLarge(
            f"the sync is {len(body)} bytes once encoded, over the {limit} byte "
            "limit for a single commit request. Refusing to split the sync "
            "across several commits, because a mirror holding part of the "
            "catalog is worse than one that was not updated. Raise "
            "--max-payload-bytes only after confirming GitHub accepts a "
            "request that size."
        )


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the installation token never leaves api.github.com.

    urllib keeps the Authorization header when it follows a redirect, and this
    token can write to the public distribution repository. Neither endpoint
    used here legitimately redirects, so a redirect is an error.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise CommitError(f"refusing to follow a redirect from {req.full_url} to {newurl}")


def _urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    opener = urllib.request.build_opener(_NoRedirects)
    try:
        with opener.open(request) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class GitHubClient:
    """The GitHub REST and GraphQL calls this helper needs."""

    def __init__(self, token: str, transport: Transport = _urllib_transport) -> None:
        self._token = token
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

    def branch_head(self, repository: str, branch: str) -> str | None:
        """Return the branch head oid, or ``None`` when the branch is absent."""

        url = f"{GITHUB_API}/repos/{repository}/git/ref/heads/{branch}"
        status, payload = self._transport("GET", url, self._headers(), None)
        if status == 404:
            return None
        if status >= 400:
            raise CommitError(f"could not read {branch}: HTTP {status} {payload!r}")
        return str(json.loads(payload)["object"]["sha"])

    def create_branch(self, repository: str, branch: str, oid: str) -> None:
        url = f"{GITHUB_API}/repos/{repository}/git/refs"
        body = json.dumps({"ref": f"refs/heads/{branch}", "sha": oid}).encode("utf-8")
        status, payload = self._transport("POST", url, self._headers(), body)
        if status >= 400:
            raise CommitError(f"could not create {branch}: HTTP {status} {payload!r}")

    def create_commit(self, body: bytes) -> dict[str, str]:
        status, payload = self._transport("POST", GRAPHQL_ENDPOINT, self._headers(), body)
        if status >= 400:
            raise CommitError(f"createCommitOnBranch failed: HTTP {status} {payload!r}")
        document = json.loads(payload)
        if document.get("errors"):
            raise CommitError(
                "createCommitOnBranch failed: "
                + json.dumps(document["errors"], sort_keys=True)
            )
        commit = document["data"]["createCommitOnBranch"]["commit"]
        return {"oid": str(commit["oid"]), "url": str(commit["url"])}


def create_signed_commit(
    *,
    repo: Path,
    repository: str,
    branch: str,
    base_oid: str,
    message: str,
    client: GitHubClient,
    remote: str = "origin",
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    log: Callable[[str], None] = print,
) -> dict[str, str] | None:
    """Commit the staged change set onto ``branch`` and return the new commit.

    Returns ``None`` when the branch already carries the staged tree, so that a
    re-run of the same source commit does not create an empty commit.
    """

    head_oid = client.branch_head(repository, branch)
    missing_branch = head_oid is None
    if head_oid is None:
        log(f"Branch {branch} does not exist; it will be created at {base_oid}.")
        head_oid = base_oid
    else:
        log(f"Branch {branch} already exists at {head_oid}.")
        ensure_commit_available(repo, remote, head_oid)

    changes = staged_file_changes(repo, head_oid)
    if not changes:
        log(f"Branch {branch} already carries this tree; no commit needed.")
        return None
    log(f"Committing {changes.summary()} onto {branch} at {head_oid}.")

    body = encode_request(
        COMMIT_MUTATION,
        {
            "input": build_commit_input(
                repository=repository,
                branch=branch,
                message=message,
                expected_head_oid=head_oid,
                changes=changes,
            )
        },
    )
    check_payload_size(body, max_payload_bytes)

    # Nothing is written to the target until the whole change set is known to
    # be valid and small enough, so a refused sync leaves no stray branch.
    if missing_branch:
        client.create_branch(repository, branch, base_oid)
    commit = client.create_commit(body)
    log(f"Created signed commit {commit['oid']} at {commit['url']}.")
    return commit


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--repository", required=True, help="owner/name of the target")
    parser.add_argument("--branch", required=True)
    parser.add_argument(
        "--base-oid",
        required=True,
        help="commit the branch is created at when it does not yet exist",
    )
    parser.add_argument("--message", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--max-payload-bytes",
        type=int,
        default=DEFAULT_MAX_PAYLOAD_BYTES,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    token = os.environ.get("GH_TOKEN", "")
    if not token:
        print("ERROR: GH_TOKEN is not set")
        return 1

    try:
        create_signed_commit(
            repo=args.repo_dir,
            repository=args.repository,
            branch=args.branch,
            base_oid=args.base_oid,
            message=args.message,
            client=GitHubClient(token),
            remote=args.remote,
            max_payload_bytes=args.max_payload_bytes,
        )
    except CommitError as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
