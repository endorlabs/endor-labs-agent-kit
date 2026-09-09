"""Turn an A2A task message into a validated :class:`AnalysisRequest`.

Input modes for v1 (§2):

* ``repo_url`` (GitHub/GitLab URL) + optional ``ref``.
* ``owner/repo`` shorthand in the message text.
* ``endor_project_id`` / ``namespace`` supplied via message ``metadata``.

The service validates and clearly rejects ambiguous requests rather than
guessing (§2, §10).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .errors import AmbiguousTargetError, InvalidParamsError
from .models import AnalysisRequest, Severity
from .validation import (
    validate_namespace,
    validate_project_id,
    validate_repo_full_name,
)

# github.com/owner/repo or gitlab.com/group/subgroup/repo, with optional
# scheme, .git suffix, and trailing path/query. The path match is greedy so a
# nested GitLab project keeps all its segments; the normalizer below decides
# which segments form the repo name.
_REPO_URL_RE = re.compile(
    r"""(?ix)
    \b(?:https?://)?
    (?P<host>github\.com|gitlab\.com)/
    (?P<path>[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+)
    (?=[\s/?#)\].,]|$)
    """
)

# Bare owner/repo shorthand (exactly one slash), not part of a URL or path.
_OWNER_REPO_RE = re.compile(r"(?<![\w./@:-])([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)(?![\w./-])")

_P0_RE = re.compile(r"(?i)\bp0\b|\bcritical\b")
_P1_RE = re.compile(r"(?i)\bp1\b|\bhigh\b")


def _text_from_message(message: Mapping[str, Any]) -> str:
    """Concatenate the text parts of an A2A message."""

    parts = message.get("parts")
    if not isinstance(parts, Sequence):
        return ""
    chunks: list[str] = []
    for part in parts:
        if not isinstance(part, Mapping):
            continue
        # A2A text parts: {"kind": "text", "text": "..."}. Tolerate the older/
        # alternate `type` discriminator some clients and A2A versions emit.
        discriminator = part.get("kind") or part.get("type")
        if discriminator == "text" and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "\n".join(chunks).strip()


# GitLab reserves these path segments for in-repo views; in legacy web URLs
# (no "/-/" separator) they mark where the project path ends.
_GITLAB_RESERVED_SEGMENTS = frozenset(
    {
        "-", "issues", "merge_requests", "pipelines", "blob", "tree", "raw",
        "commit", "commits", "wikis", "snippets", "releases", "tags",
        "branches", "jobs", "boards", "milestones",
    }
)


def _repo_full_name_from_url(host: str, path: str) -> str | None:
    """Normalize a repo URL path to the project's full name.

    GitHub projects are always ``owner/repo`` (deeper segments are in-repo
    paths). GitLab projects keep their full group/subgroup path, cut at the
    ``/-/`` separator or at the first reserved in-repo segment. Returns
    ``None`` when no two-segment project path remains — never a raw,
    un-normalized path.
    """

    segments = [seg for seg in path.split("/") if seg]
    if host.lower() == "github.com":
        segments = segments[:2]
    else:
        for index, segment in enumerate(segments):
            if segment in _GITLAB_RESERVED_SEGMENTS:
                segments = segments[:index]
                break
    if segments:
        # Sentence-final punctuation and a .git suffix are not part of the name.
        segments[-1] = segments[-1].rstrip(".")
        if segments[-1].endswith(".git"):
            segments[-1] = segments[-1][: -len(".git")]
        segments = [segment for segment in segments if segment]
    if len(segments) < 2:
        return None
    return "/".join(segments)


def parse_task_message(message: Mapping[str, Any]) -> AnalysisRequest:
    """Parse a single A2A ``message`` object into an :class:`AnalysisRequest`.

    Raises :class:`InvalidParamsError` when the message is structurally wrong
    and :class:`AmbiguousTargetError` when no repository or Endor project can
    be identified.
    """

    if not isinstance(message, Mapping):
        raise InvalidParamsError("`message` must be an object")

    text = _text_from_message(message)
    metadata = message.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}

    request = AnalysisRequest(raw_text=text)

    # 1. Structured references win over free-text ones when both are present.
    namespace = metadata.get("namespace") or metadata.get("endor_namespace")
    if isinstance(namespace, str) and namespace.strip():
        request.namespace = namespace.strip()

    project_id = metadata.get("endor_project_id") or metadata.get("project_id")
    if isinstance(project_id, str) and project_id.strip():
        request.project_id = project_id.strip()

    ref = metadata.get("ref")
    if isinstance(ref, str) and ref.strip():
        request.ref = ref.strip()

    repo_url = metadata.get("repo_url")
    if isinstance(repo_url, str) and repo_url.strip():
        request.repo_url = repo_url.strip()

    # 2. Fall back to references embedded in the natural-language text.
    if request.repo_url is None:
        url_match = _REPO_URL_RE.search(text)
        if url_match:
            request.repo_url = url_match.group(0)
            request.repo_full_name = _repo_full_name_from_url(
                url_match.group("host"), url_match.group("path")
            )
    elif request.repo_full_name is None:
        url_match = _REPO_URL_RE.search(request.repo_url)
        if url_match:
            request.repo_full_name = _repo_full_name_from_url(
                url_match.group("host"), url_match.group("path")
            )

    if request.repo_full_name is None and request.repo_url is None:
        shorthand = _OWNER_REPO_RE.search(text)
        if shorthand:
            request.repo_full_name = shorthand.group(1)

    # 3. Severity intent. Default to both P0 and P1 when unspecified.
    severities: list[Severity] = []
    if _P0_RE.search(text):
        severities.append(Severity.P0)
    if _P1_RE.search(text):
        severities.append(Severity.P1)
    request.severity_filter = severities or [Severity.P0, Severity.P1]

    # 4. Validate every value that will be interpolated into an Endor URL path
    # or filter expression, before it can reach those sinks. Malformed input is
    # a clean InvalidParams error, not a silent or injectable pass-through.
    if request.namespace is not None:
        validate_namespace(request.namespace)
    if request.repo_full_name is not None:
        validate_repo_full_name(request.repo_full_name)
    if request.project_id is not None:
        validate_project_id(request.project_id)

    # 5. Ambiguity gate: we need *some* resolvable target.
    if not any((request.repo_url, request.repo_full_name, request.project_id)):
        raise AmbiguousTargetError(
            "No repository or Endor project reference found in the request. "
            "Provide a repo URL, an owner/repo, or an Endor project/namespace "
            "(for example: 'Check acme/service-api for P0 SCA findings')."
        )

    return request
