from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import urllib.request

import pytest

from scripts.create_signed_commit import (
    CommitError,
    _NoRedirects,
    FileChanges,
    GitHubClient,
    PayloadTooLarge,
    build_commit_input,
    check_payload_size,
    create_signed_commit,
    encode_request,
    staged_file_changes,
    unexpressible_modes,
)


# A PNG header plus bytes that are not valid UTF-8, so any text round trip
# corrupts them. The mirror ships .png and .svg assets through this path.
BINARY_BLOB = b"\x89PNG\r\n\x1a\n\xff\xfe\x00\x01\x80\x81binary\x00tail"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def _write(repo: Path, path: str, data: bytes) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _mirror(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository shaped like an ai-plugins checkout at its base."""

    repo = tmp_path / "ai-plugins"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _write(repo, "catalog.json", b'{"agents": 1}\n')
    _write(repo, "agents/stale.md", b"retired agent\n")
    _write(repo, "assets/logo.png", BINARY_BLOB)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _sync(repo: Path) -> None:
    """Apply the kind of change set a sync produces, then stage it."""

    _write(repo, "catalog.json", b'{"agents": 2}\n')
    _write(repo, "agents/fresh.md", b"new agent\n")
    _write(repo, "assets/logo.png", BINARY_BLOB + b"\xf0\x9f")
    (repo / "agents" / "stale.md").unlink()
    _git(repo, "add", "-A")


class _FakeTransport:
    """Record every call and reply with queued responses."""

    def __init__(self, responses: list[tuple[int, bytes]]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str, bytes | None]] = []

    def __call__(self, method, url, headers, body):  # noqa: ANN001 - transport shape
        self.calls.append((method, url, body))
        assert headers["Authorization"] == "Bearer test-token"
        if not self._responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self._responses.pop(0)


def _commit_response() -> tuple[int, bytes]:
    return (
        200,
        json.dumps(
            {
                "data": {
                    "createCommitOnBranch": {
                        "commit": {"oid": "f" * 40, "url": "https://example.invalid/c"}
                    }
                }
            }
        ).encode("utf-8"),
    )


def test_staged_changes_carry_additions_deletions_and_exact_binary_bytes(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)

    changes = staged_file_changes(repo, base)

    assert dict(changes.additions) == {
        "catalog.json": b'{"agents": 2}\n',
        "agents/fresh.md": b"new agent\n",
        "assets/logo.png": BINARY_BLOB + b"\xf0\x9f",
    }
    assert changes.deletions == ["agents/stale.md"]


def test_binary_contents_survive_the_base64_round_trip(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)

    additions = staged_file_changes(repo, base).as_input()["additions"]
    encoded = {entry["path"]: entry["contents"] for entry in additions}

    assert base64.b64decode(encoded["assets/logo.png"]) == BINARY_BLOB + b"\xf0\x9f"


def test_staged_changes_match_what_git_commit_would_have_stored(tmp_path):
    """The API commit must reproduce the tree the old local commit produced."""

    repo, base = _mirror(tmp_path)
    _sync(repo)
    changes = staged_file_changes(repo, base)
    _git(repo, "commit", "-m", "Sync Agent Kit generated artifacts")

    committed = {
        line.split("\t", 1)[1]: line.split("\t", 1)[0]
        for line in _git(repo, "diff", "--name-status", "--no-renames", base, "HEAD").splitlines()
    }
    assert set(changes.deletions) == {path for path, status in committed.items() if status == "D"}
    assert {path for path, _ in changes.additions} == {
        path for path, status in committed.items() if status != "D"
    }
    for path, blob in changes.additions:
        assert blob == subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", f"HEAD:{path}"],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout


def test_a_rename_becomes_an_explicit_deletion_and_addition(tmp_path):
    repo, base = _mirror(tmp_path)
    (repo / "agents" / "stale.md").rename(repo / "agents" / "renamed.md")
    _git(repo, "add", "-A")

    changes = staged_file_changes(repo, base)

    assert changes.deletions == ["agents/stale.md"]
    assert dict(changes.additions) == {"agents/renamed.md": b"retired agent\n"}


def test_no_staged_change_produces_no_commit(tmp_path):
    repo, base = _mirror(tmp_path)
    _git(repo, "add", "-A")

    changes = staged_file_changes(repo, base)

    assert not changes
    assert changes.as_input() == {"additions": [], "deletions": []}


def test_oversize_payload_fails_loudly_instead_of_truncating():
    changes = FileChanges(additions=[("big.bin", b"\x00" * 4096)])
    body = encode_request(
        "mutation", {"input": build_commit_input(
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            message="Sync Agent Kit generated artifacts",
            expected_head_oid="a" * 40,
            changes=changes,
        )}
    )

    with pytest.raises(PayloadTooLarge) as caught:
        check_payload_size(body, 1024)

    assert "Refusing to split the sync" in str(caught.value)
    check_payload_size(body, len(body))


def test_oversize_payload_stops_the_job_before_any_commit_is_attempted(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)
    transport = _FakeTransport(
        [(200, json.dumps({"object": {"sha": base}}).encode("utf-8"))]
    )

    with pytest.raises(PayloadTooLarge):
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            max_payload_bytes=16,
            log=lambda _message: None,
        )

    assert [method for method, _url, _body in transport.calls] == ["GET"]


def test_commit_targets_the_existing_branch_head_as_expected_head_oid(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)
    transport = _FakeTransport(
        [
            (200, json.dumps({"object": {"sha": base}}).encode("utf-8")),
            _commit_response(),
        ]
    )

    commit = create_signed_commit(
        repo=repo,
        repository="owner/mirror",
        branch="agent-kit-sync/abc",
        base_oid=base,
        message="Sync Agent Kit generated artifacts",
        client=GitHubClient("test-token", transport),
        log=lambda _message: None,
    )

    assert commit == {"oid": "f" * 40, "url": "https://example.invalid/c"}
    _method, _url, body = transport.calls[-1]
    sent = json.loads(body)["variables"]["input"]
    assert sent["expectedHeadOid"] == base
    assert sent["branch"] == {
        "repositoryNameWithOwner": "owner/mirror",
        "branchName": "agent-kit-sync/abc",
    }
    assert sent["message"] == {"headline": "Sync Agent Kit generated artifacts"}
    assert sorted(entry["path"] for entry in sent["fileChanges"]["deletions"]) == [
        "agents/stale.md"
    ]


def test_a_missing_branch_is_created_at_the_base_commit_first(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)
    transport = _FakeTransport([(404, b"{}"), (201, b"{}"), _commit_response()])

    create_signed_commit(
        repo=repo,
        repository="owner/mirror",
        branch="agent-kit-sync/abc",
        base_oid=base,
        message="Sync Agent Kit generated artifacts",
        client=GitHubClient("test-token", transport),
        log=lambda _message: None,
    )

    methods = [method for method, _url, _body in transport.calls]
    assert methods == ["GET", "POST", "POST"]
    assert json.loads(transport.calls[1][2]) == {
        "ref": "refs/heads/agent-kit-sync/abc",
        "sha": base,
    }
    assert transport.calls[1][1].endswith("/repos/owner/mirror/git/refs")
    assert json.loads(transport.calls[2][2])["variables"]["input"]["expectedHeadOid"] == base


def test_a_branch_that_already_carries_the_tree_creates_no_empty_commit(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)
    _git(repo, "commit", "-m", "Sync Agent Kit generated artifacts")
    existing = _git(repo, "rev-parse", "HEAD")
    transport = _FakeTransport(
        [(200, json.dumps({"object": {"sha": existing}}).encode("utf-8"))]
    )

    commit = create_signed_commit(
        repo=repo,
        repository="owner/mirror",
        branch="agent-kit-sync/abc",
        base_oid=base,
        message="Sync Agent Kit generated artifacts",
        client=GitHubClient("test-token", transport),
        log=lambda _message: None,
    )

    assert commit is None
    assert [method for method, _url, _body in transport.calls] == ["GET"]


def test_a_stale_expected_head_oid_is_reported_rather_than_forced(tmp_path):
    """expectedHeadOid is the force-with-lease equivalent: a race must fail."""

    repo, base = _mirror(tmp_path)
    _sync(repo)
    rejection = json.dumps(
        {"errors": [{"message": "Expected branch to point to " + "b" * 40}]}
    ).encode("utf-8")
    transport = _FakeTransport(
        [(200, json.dumps({"object": {"sha": base}}).encode("utf-8")), (200, rejection)]
    )

    with pytest.raises(CommitError) as caught:
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            log=lambda _message: None,
        )

    assert "Expected branch to point to" in str(caught.value)


def test_a_graphql_transport_error_fails_the_job(tmp_path):
    repo, base = _mirror(tmp_path)
    _sync(repo)
    transport = _FakeTransport(
        [
            (200, json.dumps({"object": {"sha": base}}).encode("utf-8")),
            (502, b"bad gateway"),
        ]
    )

    with pytest.raises(CommitError) as caught:
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            log=lambda _message: None,
        )

    assert "HTTP 502" in str(caught.value)


def test_an_unreadable_branch_lookup_is_not_treated_as_a_missing_branch(tmp_path):
    repo, base = _mirror(tmp_path)
    transport = _FakeTransport([(500, b"server error")])

    with pytest.raises(CommitError) as caught:
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            log=lambda _message: None,
        )

    assert "HTTP 500" in str(caught.value)


def test_an_unchanged_executable_is_committed_without_complaint(tmp_path):
    """GitHub keeps the mode a path already has, so this round trips."""

    repo, base = _mirror(tmp_path)
    _write(repo, "hooks/run.sh", b"#!/bin/sh\necho v1\n")
    (repo / "hooks" / "run.sh").chmod(0o755)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add hook")
    base = _git(repo, "rev-parse", "HEAD")

    _write(repo, "hooks/run.sh", b"#!/bin/sh\necho v2\n")
    (repo / "hooks" / "run.sh").chmod(0o755)
    _git(repo, "add", "-A")

    changes = staged_file_changes(repo, base)

    assert dict(changes.additions) == {"hooks/run.sh": b"#!/bin/sh\necho v2\n"}


def test_a_newly_added_executable_fails_rather_than_losing_its_mode(tmp_path):
    """The API creates new paths as 100644, which would break a new hook."""

    repo, base = _mirror(tmp_path)
    _write(repo, "hooks/fresh.sh", b"#!/bin/sh\necho hi\n")
    (repo / "hooks" / "fresh.sh").chmod(0o755)
    _git(repo, "add", "-A")

    with pytest.raises(CommitError) as caught:
        staged_file_changes(repo, base)

    message = str(caught.value)
    assert "hooks/fresh.sh" in message
    assert "100755" in message
    assert "cannot set a file mode" in message


def test_a_mode_change_on_an_existing_path_fails(tmp_path):
    repo, base = _mirror(tmp_path)
    (repo / "agents" / "stale.md").chmod(0o755)
    _git(repo, "add", "-A")

    with pytest.raises(CommitError) as caught:
        staged_file_changes(repo, base)

    assert "agents/stale.md (100644 becomes 100755)" in str(caught.value)


def test_unexpressible_modes_accepts_what_the_api_can_represent():
    assert unexpressible_modes([("new.md", "000000", "100644")]) == []
    assert unexpressible_modes([("hook.sh", "100755", "100755")]) == []
    assert unexpressible_modes([("link", "000000", "120000")]) == [
        "link (new file needs mode 120000)"
    ]
    assert unexpressible_modes([("hook.sh", "100755", "100644")]) == [
        "hook.sh (100755 becomes 100644)"
    ]


def test_a_refused_sync_leaves_no_stray_branch_behind(tmp_path):
    """Nothing is written to the mirror until the change set is known good."""

    repo, base = _mirror(tmp_path)
    _sync(repo)
    transport = _FakeTransport([(404, b"{}")])

    with pytest.raises(PayloadTooLarge):
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            max_payload_bytes=16,
            log=lambda _message: None,
        )

    assert [method for method, _url, _body in transport.calls] == ["GET"]


def test_an_unexpressible_mode_is_caught_before_the_branch_is_created(tmp_path):
    repo, base = _mirror(tmp_path)
    _write(repo, "hooks/fresh.sh", b"#!/bin/sh\necho hi\n")
    (repo / "hooks" / "fresh.sh").chmod(0o755)
    _git(repo, "add", "-A")
    transport = _FakeTransport([(404, b"{}")])

    with pytest.raises(CommitError):
        create_signed_commit(
            repo=repo,
            repository="owner/mirror",
            branch="agent-kit-sync/abc",
            base_oid=base,
            message="Sync Agent Kit generated artifacts",
            client=GitHubClient("test-token", transport),
            log=lambda _message: None,
        )

    assert [method for method, _url, _body in transport.calls] == ["GET"]


def test_a_redirect_is_refused_so_the_token_stays_on_the_api_host():
    """urllib keeps Authorization across hosts, so redirects must not be followed."""

    handler = _NoRedirects()

    with pytest.raises(CommitError) as caught:
        handler.redirect_request(
            urllib.request.Request("https://api.github.com/graphql"),
            None,
            302,
            "Found",
            {},
            "https://example.invalid/graphql",
        )

    assert "refusing to follow a redirect" in str(caught.value)
