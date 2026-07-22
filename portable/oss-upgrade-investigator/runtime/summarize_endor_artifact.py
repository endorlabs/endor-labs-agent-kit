#!/usr/bin/env python3
"""Summarize a large Endor Agent API artifact without exposing its rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Sequence


SCHEMA_VERSION = "endor.agent-artifact-summary/v1"
DEFAULT_COLLECTION_PATH = "list.objects"
DEFAULT_UNIQUE_FIELD = "uuid"
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
DEFAULT_CAPTURE_TIMEOUT_SECONDS = 300


class ArtifactSummaryError(ValueError):
    """A safe, machine-readable artifact validation failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def summarize_artifact(
    artifact: str | Path,
    *,
    collection_path: str = DEFAULT_COLLECTION_PATH,
    unique_field: str = DEFAULT_UNIQUE_FIELD,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    """Read one artifact once and return compact integrity metadata.

    The returned record never contains row values. The default contract accepts
    the JSON envelope emitted by ``endorctl agent api ... list -o json`` and
    requires a unique, non-empty UUID for each object.
    """

    path = Path(artifact).expanduser().absolute()
    if max_bytes <= 0:
        raise ArtifactSummaryError("invalid_max_bytes", "max_bytes must be positive")
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise ArtifactSummaryError("artifact_unavailable", "artifact is not readable") from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise ArtifactSummaryError("artifact_symlink_rejected", "artifact must not be a symlink")
    if not stat.S_ISREG(path_stat.st_mode):
        raise ArtifactSummaryError("artifact_not_regular", "artifact must be a regular file")
    if path_stat.st_size > max_bytes:
        raise ArtifactSummaryError(
            "artifact_too_large",
            f"artifact exceeds configured maximum of {max_bytes} bytes",
        )

    try:
        with path.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            data = handle.read(max_bytes + 1)
            final_stat = os.fstat(handle.fileno())
    except OSError as exc:
        raise ArtifactSummaryError("artifact_unavailable", "artifact is not readable") from exc
    if len(data) > max_bytes:
        raise ArtifactSummaryError(
            "artifact_too_large",
            f"artifact exceeds configured maximum of {max_bytes} bytes",
        )
    if (
        opened_stat.st_dev != final_stat.st_dev
        or opened_stat.st_ino != final_stat.st_ino
        or opened_stat.st_size != final_stat.st_size
        or opened_stat.st_mtime_ns != final_stat.st_mtime_ns
        or len(data) != final_stat.st_size
    ):
        raise ArtifactSummaryError(
            "artifact_changed_during_read",
            "artifact changed while it was being summarized",
        )

    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactSummaryError("invalid_json", "artifact is not valid JSON") from exc
    objects = _mapping_path(payload, collection_path)
    if not isinstance(objects, list):
        raise ArtifactSummaryError(
            "collection_not_array",
            f"collection path {collection_path!r} must contain an array",
        )

    values: list[str] = []
    missing_unique_count = 0
    for row in objects:
        if not isinstance(row, dict):
            raise ArtifactSummaryError(
                "row_not_object",
                "every collection row must be a JSON object",
            )
        value = _optional_mapping_path(row, unique_field)
        if not isinstance(value, str) or not value.strip():
            missing_unique_count += 1
        else:
            values.append(value)
    unique_count = len(set(values))
    duplicate_count = len(values) - unique_count
    if missing_unique_count:
        raise ArtifactSummaryError(
            "missing_unique_values",
            f"{missing_unique_count} rows are missing a non-empty {unique_field!r}",
        )
    if duplicate_count:
        raise ArtifactSummaryError(
            "duplicate_unique_values",
            f"{duplicate_count} rows contain duplicate {unique_field!r} values",
        )

    return {
        "artifact_ref": str(path),
        "bytes": len(data),
        "collection_path": collection_path,
        "duplicate_count": duplicate_count,
        "format": "json",
        "missing_unique_count": missing_unique_count,
        "row_count": len(objects),
        "schema_version": SCHEMA_VERSION,
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": "valid",
        "unique_count": unique_count,
        "unique_field": unique_field,
    }


def capture_and_summarize(
    command: Sequence[str],
    *,
    artifact_dir: str | Path | None = None,
    collection_path: str = DEFAULT_COLLECTION_PATH,
    unique_field: str = DEFAULT_UNIQUE_FIELD,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: int = DEFAULT_CAPTURE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Execute one read-only Agent API list directly into a protected artifact."""

    normalized = tuple(command[1:] if command and command[0] == "--" else command)
    _validate_capture_command(normalized)
    if timeout_seconds <= 0:
        raise ArtifactSummaryError("invalid_timeout", "timeout_seconds must be positive")

    if artifact_dir is None:
        destination = Path(tempfile.gettempdir()) / "endor-agent-artifacts"
    else:
        destination = Path(artifact_dir).expanduser().absolute()
    try:
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, artifact_name = tempfile.mkstemp(
            prefix="agent-api-",
            suffix=".json",
            dir=destination,
        )
        os.fchmod(descriptor, 0o600)
    except OSError as exc:
        raise ArtifactSummaryError(
            "artifact_create_failed",
            "unable to create a protected host artifact",
        ) from exc

    artifact = Path(artifact_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            completed = subprocess.run(
                normalized,
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_timeout",
            f"endorctl Agent API capture exceeded {timeout_seconds} seconds",
        ) from exc
    except OSError as exc:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_unavailable",
            "unable to execute the selected endorctl binary",
        ) from exc
    if completed.returncode != 0:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_failed",
            f"endorctl Agent API capture exited with status {completed.returncode}",
        )

    try:
        return summarize_artifact(
            artifact,
            collection_path=collection_path,
            unique_field=unique_field,
            max_bytes=max_bytes,
        )
    except ArtifactSummaryError:
        artifact.unlink(missing_ok=True)
        raise


def _validate_capture_command(command: Sequence[str]) -> None:
    if len(command) < 6 or Path(command[0]).name != "endorctl":
        raise ArtifactSummaryError(
            "invalid_capture_command",
            "capture requires a direct endorctl Agent API list command",
        )
    if tuple(command[1:3]) != ("agent", "api") or "list" not in command[3:]:
        raise ArtifactSummaryError(
            "invalid_capture_command",
            "capture permits only endorctl agent api list",
        )
    if "--agent-id" not in command or not _option_value(command, "--agent-id"):
        raise ArtifactSummaryError(
            "missing_agent_id",
            "capture requires a canonical --agent-id",
        )
    if not any(option in command for option in ("-r", "--resource")):
        raise ArtifactSummaryError(
            "missing_resource",
            "capture requires an explicit resource",
        )
    if "--field-mask" not in command or not _option_value(command, "--field-mask"):
        raise ArtifactSummaryError(
            "missing_field_mask",
            "capture requires an explicit minimal field mask",
        )
    if "--count" in command:
        raise ArtifactSummaryError(
            "count_capture_rejected",
            "capture is for row artifacts, not --count output",
        )
    output_format = _option_value(command, "-o") or _option_value(command, "--output")
    if output_format != "json":
        raise ArtifactSummaryError(
            "invalid_output_format",
            "capture requires JSON output",
        )


def _option_value(command: Sequence[str], option: str) -> str:
    try:
        index = command.index(option)
    except ValueError:
        return ""
    if index + 1 >= len(command):
        return ""
    value = command[index + 1]
    return "" if value.startswith("-") else value


def _mapping_path(payload: Any, dotted_path: str) -> Any:
    value = payload
    for segment in _path_segments(dotted_path):
        if not isinstance(value, dict) or segment not in value:
            raise ArtifactSummaryError(
                "missing_collection_path",
                f"artifact is missing collection path {dotted_path!r}",
            )
        value = value[segment]
    return value


def _optional_mapping_path(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for segment in _path_segments(dotted_path):
        if not isinstance(value, dict) or segment not in value:
            return None
        value = value[segment]
    return value


def _path_segments(dotted_path: str) -> tuple[str, ...]:
    segments = tuple(dotted_path.split("."))
    if not segments or any(not segment for segment in segments):
        raise ArtifactSummaryError("invalid_path", "JSON paths must use non-empty dot segments")
    return segments


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="summarize_endor_artifact.py",
        description="Validate and summarize one Endor Agent API JSON artifact.",
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    summarize = subparsers.add_parser("summarize", help="Summarize an existing artifact")
    summarize.add_argument("artifact", help="Path to the host artifact JSON file")
    capture = subparsers.add_parser(
        "capture",
        help="Capture one endorctl Agent API list and summarize it without model-visible rows",
    )
    capture.add_argument("--artifact-dir", help="Protected host directory for the raw artifact")
    capture.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_CAPTURE_TIMEOUT_SECONDS,
        help=f"endorctl timeout in seconds (default: {DEFAULT_CAPTURE_TIMEOUT_SECONDS})",
    )
    capture.add_argument("command", nargs=argparse.REMAINDER)
    for command_parser in (summarize, capture):
        _add_summary_options(command_parser)
    return parser


def _add_summary_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--collection-path",
        default=DEFAULT_COLLECTION_PATH,
        help=f"JSON collection path (default: {DEFAULT_COLLECTION_PATH})",
    )
    parser.add_argument(
        "--unique-field",
        default=DEFAULT_UNIQUE_FIELD,
        help=f"Unique field required on every row (default: {DEFAULT_UNIQUE_FIELD})",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Maximum artifact size (default: {DEFAULT_MAX_BYTES})",
    )
def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments and arguments[0] not in {"capture", "summarize", "-h", "--help"}:
        arguments.insert(0, "summarize")
    args = _parser().parse_args(arguments)
    try:
        if args.operation == "capture":
            summary = capture_and_summarize(
                args.command,
                artifact_dir=args.artifact_dir,
                collection_path=args.collection_path,
                unique_field=args.unique_field,
                max_bytes=args.max_bytes,
                timeout_seconds=args.timeout,
            )
        else:
            summary = summarize_artifact(
                args.artifact,
                collection_path=args.collection_path,
                unique_field=args.unique_field,
                max_bytes=args.max_bytes,
            )
    except ArtifactSummaryError as exc:
        error = {
            "error_code": exc.code,
            "message": exc.message,
            "schema_version": SCHEMA_VERSION,
            "status": "invalid",
        }
        sys.stderr.write(json.dumps(error, separators=(",", ":"), sort_keys=True) + "\n")
        return 2
    sys.stdout.write(json.dumps(summary, separators=(",", ":"), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the installed helper
    raise SystemExit(main())
