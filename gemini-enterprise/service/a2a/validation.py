"""Input validation for values that flow into Endor URL paths and filters.

Message-supplied identifiers reach two injection-sensitive sinks:

* the request **URL path** ``/v1/namespaces/{namespace}/{resource}`` — an
  unvalidated ``namespace`` allows path traversal / cross-namespace access;
* the Endor **filter** expression ``spec.git.full_name=="{repo}"`` /
  ``spec.project_uuid=="{uuid}"`` — an unvalidated value can break out of the
  quoted literal and alter query semantics (filter injection).

These validators pin every such value to a strict allowlist charset *before* it
is interpolated. They are applied at the parser boundary (so bad input becomes a
clean JSON-RPC error) and again in the REST client (defense in depth — the
client does not trust its caller).
"""

from __future__ import annotations

import re

from .errors import InvalidParamsError

# Repo full name: two-or-more path segments of an allowlist charset. The charset
# excludes quotes, whitespace, and filter operators, so the value cannot escape
# a quoted filter literal.
REPO_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+$")
# Namespace: a single path segment (no slash) of the same allowlist charset, so
# it cannot traverse or restructure the URL path.
NAMESPACE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Endor object UUID: exactly 24 lowercase hex characters.
PROJECT_UUID_RE = re.compile(r"^[0-9a-f]{24}$")

_DOT_SEGMENTS = frozenset({".", ".."})


def is_valid_namespace(value: str) -> bool:
    # fullmatch: unlike `$`, it cannot be satisfied with a trailing newline.
    if not isinstance(value, str) or not NAMESPACE_RE.fullmatch(value):
        return False
    return value not in _DOT_SEGMENTS


def is_valid_repo_full_name(value: str) -> bool:
    if not isinstance(value, str) or not REPO_FULL_NAME_RE.fullmatch(value):
        return False
    return all(segment not in _DOT_SEGMENTS for segment in value.split("/"))


def is_valid_project_uuid(value: object) -> bool:
    # `object` because one caller checks an Endor-returned value, which is not
    # guaranteed to be a string.
    return isinstance(value, str) and bool(PROJECT_UUID_RE.fullmatch(value))


def validate_namespace(value: str) -> str:
    if not is_valid_namespace(value):
        raise InvalidParamsError(
            "Invalid namespace: only letters, digits, '.', '_' and '-' are allowed."
        )
    return value


def validate_repo_full_name(value: str) -> str:
    if not is_valid_repo_full_name(value):
        raise InvalidParamsError(
            "Invalid repository reference: expected 'owner/repo' using letters, "
            "digits, '.', '_', '-' and '/'."
        )
    return value


def validate_project_id(value: str) -> str:
    if not is_valid_project_uuid(value):
        raise InvalidParamsError(
            "Invalid project id: expected a 24-character lowercase hex Endor UUID."
        )
    return value
