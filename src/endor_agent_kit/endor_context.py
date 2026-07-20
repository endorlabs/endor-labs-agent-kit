"""Endor Labs upstream context provenance and freshness checks."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

DEFAULT_CONTEXT_PATH = Path("source/endor-context/provenance.json")
DEFAULT_OPENAPI_SPEC_PATH = Path("source/endor-context/openapiv2.swagger.json")
DEFAULT_OPENAPI_URL = "https://api.endorlabs.com/download/openapiv2.swagger.json"
DEFAULT_META_VERSION_URL = "https://api.endorlabs.com/meta/version"
DEFAULT_TIMEOUT_SECONDS = 120
USER_AGENT = "endor-agent-kit-context-provenance/0.1"

DEFAULT_DOCS = (
    {
        "id": "endorctl-install-auth",
        "purpose": "endorctl installation, configuration, and authentication guidance",
        "url": "https://docs.endorlabs.com/developers-api/cli/install-and-configure",
    },
    {
        "id": "endorctl-init",
        "purpose": "endorctl init authentication command reference",
        "url": "https://docs.endorlabs.com/developers-api/cli/commands/init",
    },
    {
        "id": "rest-api-authentication",
        "purpose": "Endor Labs REST API authentication guidance",
        "url": "https://docs.endorlabs.com/developers-api/rest-api/authentication",
    },
    {
        "id": "api-query-builder",
        "purpose": "endorctl API query builder guidance",
        "url": "https://docs.endorlabs.com/developers-api/rest-api/api-query-builder",
    },
    {
        "id": "pr-scans",
        "purpose": "pull request scan behavior and troubleshooting",
        "url": "https://docs.endorlabs.com/scan/pr-scans",
    },
    {
        "id": "container-scanning",
        "purpose": "container scan setup and troubleshooting",
        "url": "https://docs.endorlabs.com/scan/containers",
    },
    {
        "id": "artifact-signing",
        "purpose": "artifact signing release validation reference",
        "url": "https://docs.endorlabs.com/scan/containers/artifact-signing",
    },
    {
        "id": "endorctl-exit-codes",
        "purpose": "endorctl exit-code troubleshooting reference",
        "url": "https://docs.endorlabs.com/best-practices/troubleshooting/endorctl-exitcodes",
    },
)

FetchBytes = Callable[[str], bytes]
FetchJson = Callable[[str], dict[str, Any]]
FetchUrlStatus = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class EndorContextReport:
    """Result of checking committed Endor context provenance."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def refresh_endor_context(
    context_path: Path = DEFAULT_CONTEXT_PATH,
    *,
    spec_path: Path | None = DEFAULT_OPENAPI_SPEC_PATH,
    checked_at: str | None = None,
    fetch_bytes: FetchBytes | None = None,
    fetch_json: FetchJson | None = None,
    fetch_url_status: FetchUrlStatus | None = None,
) -> dict[str, Any]:
    """Fetch current upstream provenance and write it to ``context_path``."""

    fetch_bytes = fetch_bytes or _fetch_url_bytes
    openapi_bytes = fetch_bytes(DEFAULT_OPENAPI_URL)

    def pinned_fetch_bytes(url: str) -> bytes:
        if url == DEFAULT_OPENAPI_URL:
            return openapi_bytes
        return fetch_bytes(url)

    payload = build_endor_context_payload(
        checked_at=checked_at,
        fetch_bytes=pinned_fetch_bytes,
        fetch_json=fetch_json,
        fetch_url_status=fetch_url_status,
    )
    write_endor_context(context_path, payload)
    resolved_spec_path = default_spec_path_for_context(context_path, spec_path)
    if resolved_spec_path is not None:
        write_openapi_spec(resolved_spec_path, openapi_bytes)
    return payload


def build_endor_context_payload(
    *,
    checked_at: str | None = None,
    fetch_bytes: FetchBytes | None = None,
    fetch_json: FetchJson | None = None,
    fetch_url_status: FetchUrlStatus | None = None,
) -> dict[str, Any]:
    """Build deterministic Endor upstream provenance from live sources."""

    checked_at = checked_at or date.today().isoformat()
    fetch_bytes = fetch_bytes or _fetch_url_bytes
    fetch_json = fetch_json or _fetch_url_json
    fetch_url_status = fetch_url_status or _fetch_url_status

    openapi_bytes = fetch_bytes(DEFAULT_OPENAPI_URL)
    meta = fetch_json(DEFAULT_META_VERSION_URL)
    service = meta.get("Service") if isinstance(meta.get("Service"), dict) else {}

    docs: list[dict[str, Any]] = []
    for doc in DEFAULT_DOCS:
        status = fetch_url_status(str(doc["url"]))
        entry = {
            "id": doc["id"],
            "purpose": doc["purpose"],
            "url": doc["url"],
            "status": status.get("status"),
            "final_url": status.get("final_url"),
        }
        if status.get("error"):
            entry["error"] = status["error"]
        docs.append(entry)

    payload = {
        "schema_version": 1,
        "checked_at": checked_at,
        "openapi": {
            "url": DEFAULT_OPENAPI_URL,
            "sha256": hashlib.sha256(openapi_bytes).hexdigest(),
            "bytes": len(openapi_bytes),
            "failure_mode": "blocking",
        },
        "meta_version": {
            "url": DEFAULT_META_VERSION_URL,
            "client_version": meta.get("ClientVersion"),
            "service_version": service.get("Version"),
            "service_sha": service.get("SHA"),
            "failure_mode": "warning",
        },
        "docs": docs,
    }
    report = validate_endor_context_payload(payload)
    if not report.ok:
        raise ValueError("cannot refresh invalid Endor context: " + "; ".join(report.errors))
    doc_errors = _doc_status_errors(payload)
    if doc_errors:
        raise ValueError("cannot refresh Endor context with stale docs: " + "; ".join(doc_errors))
    return payload


def verify_endor_context(
    context_path: Path = DEFAULT_CONTEXT_PATH,
    *,
    spec_path: Path | None = DEFAULT_OPENAPI_SPEC_PATH,
    upstream: bool = False,
    fetch_bytes: FetchBytes | None = None,
    fetch_json: FetchJson | None = None,
    fetch_url_status: FetchUrlStatus | None = None,
) -> EndorContextReport:
    """Validate committed Endor context and optionally compare it to upstream."""

    try:
        payload = load_endor_context(context_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return EndorContextReport((f"{context_path}: {exc}",), ())

    report = validate_endor_context_payload(payload)
    errors = list(report.errors)
    warnings = list(report.warnings)
    errors.extend(local_openapi_spec_errors(payload, context_path=context_path, spec_path=spec_path))
    if errors or not upstream:
        return EndorContextReport(tuple(errors), tuple(warnings))

    fetch_bytes = fetch_bytes or _fetch_url_bytes
    fetch_json = fetch_json or _fetch_url_json
    fetch_url_status = fetch_url_status or _fetch_url_status

    openapi = payload["openapi"]
    try:
        current_openapi = fetch_bytes(openapi["url"])
    except Exception as exc:
        errors.append(f"openapi fetch failed for {openapi['url']}: {exc}")
    else:
        current_sha = hashlib.sha256(current_openapi).hexdigest()
        if current_sha != openapi["sha256"]:
            errors.append(
                "openapi sha256 drift: "
                f"committed {openapi['sha256']} but upstream {current_sha} at {openapi['url']}"
            )
        if len(current_openapi) != openapi["bytes"]:
            warnings.append(
                "openapi byte count drift: "
                f"committed {openapi['bytes']} but upstream {len(current_openapi)} at {openapi['url']}"
            )

    meta = payload["meta_version"]
    try:
        current_meta = fetch_json(meta["url"])
    except Exception as exc:
        warnings.append(f"meta version fetch failed for {meta['url']}: {exc}")
    else:
        current_service = (
            current_meta.get("Service") if isinstance(current_meta.get("Service"), dict) else {}
        )
        current_client = current_meta.get("ClientVersion")
        current_service_version = current_service.get("Version")
        current_service_sha = current_service.get("SHA")
        if current_client != meta.get("client_version"):
            warnings.append(
                "Endor client version drift: "
                f"committed {meta.get('client_version')} but upstream {current_client}"
            )
        if current_service_version != meta.get("service_version"):
            warnings.append(
                "Endor service version drift: "
                f"committed {meta.get('service_version')} but upstream {current_service_version}"
            )
        if current_service_sha != meta.get("service_sha"):
            warnings.append(
                "Endor service SHA drift: "
                f"committed {meta.get('service_sha')} but upstream {current_service_sha}"
            )

    for doc in payload["docs"]:
        try:
            current = fetch_url_status(doc["url"])
        except Exception as exc:
            errors.append(f"docs fetch failed for {doc['id']} at {doc['url']}: {exc}")
            continue
        status = current.get("status")
        final_url = current.get("final_url")
        if status != doc["status"]:
            errors.append(
                f"docs status drift for {doc['id']}: "
                f"committed {doc['status']} but upstream {status} at {doc['url']}"
            )
        if final_url != doc["final_url"]:
            errors.append(
                f"docs canonical URL drift for {doc['id']}: "
                f"committed {doc['final_url']} but upstream {final_url}"
            )
        if current.get("error"):
            errors.append(f"docs fetch error for {doc['id']}: {current['error']}")

    return EndorContextReport(tuple(errors), tuple(warnings))


def validate_endor_context_payload(payload: object) -> EndorContextReport:
    """Validate the committed provenance JSON shape without network access."""

    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return EndorContextReport(("payload must be a JSON object",), ())
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    checked_at = payload.get("checked_at")
    if not isinstance(checked_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", checked_at):
        errors.append("checked_at must be an ISO date string")

    _validate_openapi(payload.get("openapi"), errors)
    _validate_meta_version(payload.get("meta_version"), errors, warnings)
    _validate_docs(payload.get("docs"), errors)
    errors.extend(_doc_status_errors(payload))
    return EndorContextReport(tuple(errors), tuple(warnings))


def load_endor_context(context_path: Path = DEFAULT_CONTEXT_PATH) -> dict[str, Any]:
    data = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Endor context provenance must be a JSON object")
    return data


def write_endor_context(context_path: Path, payload: dict[str, Any]) -> None:
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_openapi_spec(spec_path: Path, openapi_bytes: bytes) -> None:
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_bytes(openapi_bytes)


def local_openapi_spec_errors(
    payload: dict[str, Any],
    *,
    context_path: Path,
    spec_path: Path | None,
) -> list[str]:
    resolved = default_spec_path_for_context(context_path, spec_path)
    if resolved is None:
        return []
    if not resolved.exists():
        if default_context_location(context_path):
            return [f"{resolved}: missing pinned OpenAPI spec"]
        return []
    data = resolved.read_bytes()
    openapi = payload.get("openapi") if isinstance(payload.get("openapi"), dict) else {}
    errors: list[str] = []
    sha = hashlib.sha256(data).hexdigest()
    if sha != openapi.get("sha256"):
        errors.append(f"{resolved}: sha256 does not match provenance openapi.sha256")
    if len(data) != openapi.get("bytes"):
        errors.append(f"{resolved}: byte count does not match provenance openapi.bytes")
    return errors


def default_spec_path_for_context(context_path: Path, spec_path: Path | None) -> Path | None:
    if spec_path is None:
        return None
    if spec_path.is_absolute():
        return spec_path
    if spec_path == DEFAULT_OPENAPI_SPEC_PATH:
        return context_path.parent / spec_path.name
    return spec_path


def default_context_location(context_path: Path) -> bool:
    return context_path.as_posix().endswith(DEFAULT_CONTEXT_PATH.as_posix())


def _validate_openapi(value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("openapi must be a JSON object")
        return
    if not _is_http_url(value.get("url")):
        errors.append("openapi.url must be an HTTP URL")
    sha = value.get("sha256")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        errors.append("openapi.sha256 must be a lowercase SHA-256 hex digest")
    byte_count = value.get("bytes")
    if not isinstance(byte_count, int) or byte_count <= 0:
        errors.append("openapi.bytes must be a positive integer")
    if value.get("failure_mode") != "blocking":
        errors.append("openapi.failure_mode must be blocking")


def _validate_meta_version(value: object, errors: list[str], warnings: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("meta_version must be a JSON object")
        return
    if not _is_http_url(value.get("url")):
        errors.append("meta_version.url must be an HTTP URL")
    if value.get("failure_mode") != "warning":
        errors.append("meta_version.failure_mode must be warning")
    for key in ("client_version", "service_version"):
        version = value.get(key)
        if not isinstance(version, str) or not version:
            errors.append(f"meta_version.{key} must be a non-empty string")
        elif not version.startswith("v"):
            warnings.append(f"meta_version.{key} does not start with v")
    service_sha = value.get("service_sha")
    if not isinstance(service_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", service_sha):
        errors.append("meta_version.service_sha must be a lowercase Git SHA")


def _validate_docs(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("docs must be a non-empty list")
        return
    seen_ids: set[str] = set()
    for index, doc in enumerate(value):
        if not isinstance(doc, dict):
            errors.append(f"docs[{index}] must be a JSON object")
            continue
        doc_id = doc.get("id")
        if not isinstance(doc_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", doc_id):
            errors.append(f"docs[{index}].id must be a slug")
        elif doc_id in seen_ids:
            errors.append(f"docs[{index}].id duplicates {doc_id}")
        else:
            seen_ids.add(doc_id)
        if not isinstance(doc.get("purpose"), str) or not doc["purpose"]:
            errors.append(f"docs[{index}].purpose must be a non-empty string")
        if not _is_http_url(doc.get("url")):
            errors.append(f"docs[{index}].url must be an HTTP URL")
        if not isinstance(doc.get("status"), int):
            errors.append(f"docs[{index}].status must be an integer")
        if not _is_http_url(doc.get("final_url")):
            errors.append(f"docs[{index}].final_url must be an HTTP URL")


def _doc_status_errors(payload: object) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("docs"), list):
        return []
    errors: list[str] = []
    for doc in payload["docs"]:
        if not isinstance(doc, dict):
            continue
        if doc.get("status") != 200:
            errors.append(
                f"docs URL {doc.get('id', '<unknown>')} must resolve with status 200, "
                f"got {doc.get('status')}"
            )
        if doc.get("url") != doc.get("final_url"):
            errors.append(
                f"docs URL {doc.get('id', '<unknown>')} must be canonical without redirect: "
                f"{doc.get('url')} -> {doc.get('final_url')}"
            )
    return errors


def _is_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def _fetch_url_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
        return response.read()


def _fetch_url_json(url: str) -> dict[str, Any]:
    data = _fetch_url_bytes(url)
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{url} did not return a JSON object")
    return payload


def _fetch_url_status(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            response.read(1)
            return {
                "status": getattr(response, "status", response.getcode()),
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "final_url": exc.geturl(),
            "error": str(exc.reason),
        }
