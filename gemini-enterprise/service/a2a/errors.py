"""Typed errors that map cleanly onto JSON-RPC error responses.

The design doc (§10) requires that auth failure, an unrecognized or ambiguous
repo reference, and an unauthorized namespace surface as *clear JSON-RPC error
responses* -- never silent empty results. Each error below carries the JSON-RPC
``code`` and a stable ``message`` the transport layer serializes verbatim.
"""

from __future__ import annotations

# Standard JSON-RPC 2.0 codes (subset we emit).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# A2A-aligned codes (A2A reserves -32001 for TaskNotFound).
TASK_NOT_FOUND = -32001

# Application-specific codes (reserved -32000..-32099 implementation-defined range).
AMBIGUOUS_TARGET = -32010
AUTH_FAILED = -32011
NAMESPACE_NOT_AUTHORIZED = -32012


class AgentError(Exception):
    """Base class for errors that become JSON-RPC error responses."""

    code: int = INTERNAL_ERROR

    def __init__(self, message: str, *, data: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.data = data

    def to_jsonrpc(self) -> dict[str, object]:
        error: dict[str, object] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


class InvalidParamsError(AgentError):
    code = INVALID_PARAMS


class MethodNotFoundError(AgentError):
    code = METHOD_NOT_FOUND


class TaskNotFoundError(AgentError):
    """A referenced task id is not known to this service."""

    code = TASK_NOT_FOUND


class AmbiguousTargetError(AgentError):
    """The task did not name a resolvable repository or Endor project."""

    code = AMBIGUOUS_TARGET


class AuthenticationError(AgentError):
    """Endor authentication was missing or rejected."""

    code = AUTH_FAILED


class NamespaceNotAuthorizedError(AgentError):
    """The caller is not authorized for the requested Endor namespace."""

    code = NAMESPACE_NOT_AUTHORIZED
