#!/usr/bin/env python3
"""Validate and deterministically package the Codex skills-only submission."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import sys
import zipfile


PLUGIN_NAME = "endor-labs-agent-kit"
PACKAGE_PATH = Path("plugins") / "codex-directory" / PLUGIN_NAME
CHANNEL = "official-directory"
VALIDATOR_VERSION = "1"
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 5000
CANONICAL_SKILL_IDS = (
    "ai-sast-remediation",
    "cicd-posture",
    "configuration-automation",
    "dependency-reviewer",
    "findings-browser",
    "malware-responder",
    "oss-upgrade-investigator",
    "remediation-planning",
    "sca-remediation",
    "troubleshooting",
    "vulnerability-explainer",
)
REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "scripts/summarize_endor_artifact.py",
)
FORBIDDEN_COMPONENTS = (
    ".app.json",
    ".mcp.json",
    "agents",
    "bundled-skills",
    "hooks",
    "runtime",
    "scripts/install_codex_agents.py",
)
FORBIDDEN_TEXT = (
    "matt-staging",
    "/Users/",
    "\\Users\\",
    "composer-2.5",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_digest(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def validate_package(root: Path) -> dict[str, object]:
    root = root.resolve()
    package = root / PACKAGE_PATH
    errors: list[str] = []
    manifest_path = package / ".codex-plugin" / "plugin.json"
    catalog_manifest_path = _catalog_manifest_path(root)

    if not package.is_dir():
        errors.append(f"{PACKAGE_PATH.as_posix()}: missing package directory")
        return _report(root, package, errors, None, None)
    if package.is_symlink():
        errors.append(f"{PACKAGE_PATH.as_posix()}: package root must not be a symlink")

    files = sorted(path for path in package.rglob("*") if path.is_file() or path.is_symlink())
    if len(files) > MAX_ARCHIVE_ENTRIES:
        errors.append(f"package has {len(files)} files; maximum is {MAX_ARCHIVE_ENTRIES}")

    total_bytes = 0
    for path in files:
        relative = path.relative_to(package).as_posix()
        if path.is_symlink():
            errors.append(f"{relative}: symlinks are not permitted")
            continue
        total_bytes += path.stat().st_size
        if not _safe_relative_path(relative):
            errors.append(f"{relative}: unsafe package path")
        if path.suffix.lower() in {".md", ".json", ".yaml", ".yml", ".py", ".toml", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"{relative}: expected UTF-8 text")
                continue
            for forbidden in FORBIDDEN_TEXT:
                if forbidden in text:
                    errors.append(f"{relative}: contains forbidden public value {forbidden!r}")
    if total_bytes > MAX_ARCHIVE_BYTES:
        errors.append(f"package is {total_bytes} bytes; maximum is {MAX_ARCHIVE_BYTES}")

    actual_top_level = {path.name for path in package.iterdir()}
    expected_top_level = {".codex-plugin", "assets", "skills"}
    if actual_top_level != expected_top_level:
        errors.append(
            "package top-level entries must be exactly "
            f"{sorted(expected_top_level)}; got {sorted(actual_top_level)}"
        )
    for component in FORBIDDEN_COMPONENTS:
        if (package / component).exists():
            errors.append(f"{component}: forbidden in skills-only package")

    plugin_manifest = _load_json(manifest_path, errors, manifest_path.relative_to(root).as_posix())
    if plugin_manifest is not None:
        _validate_plugin_manifest(plugin_manifest, package, errors)

    skills_root = package / "skills"
    skill_ids = tuple(
        sorted(path.name for path in skills_root.iterdir() if path.is_dir())
    ) if skills_root.is_dir() else ()
    if skill_ids != CANONICAL_SKILL_IDS:
        errors.append(
            f"skills: expected {list(CANONICAL_SKILL_IDS)}, got {list(skill_ids)}"
        )
    for skill_id in CANONICAL_SKILL_IDS:
        _validate_skill(package / "skills" / skill_id, skill_id, errors)

    package_record = None
    catalog_manifest = _load_json(
        catalog_manifest_path,
        errors,
        "manifest.json",
    )
    if catalog_manifest is not None:
        package_record = _official_package_record(catalog_manifest, errors)
        if package_record is not None:
            _validate_catalog_artifacts(root, package, package_record, errors)

    return _report(root, package, errors, plugin_manifest, package_record)


def _validate_plugin_manifest(
    manifest: dict[str, object],
    package: Path,
    errors: list[str],
) -> None:
    if manifest.get("name") != PLUGIN_NAME:
        errors.append(f"plugin.json: name must be {PLUGIN_NAME!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        errors.append("plugin.json: version must be semantic version text")
    if manifest.get("skills") != "./skills/":
        errors.append("plugin.json: skills must be './skills/'")
    for key in ("hooks", "mcpServers", "apps"):
        if key in manifest:
            errors.append(f"plugin.json: {key} is forbidden in skills-only submissions")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json: interface must be an object")
        return
    _bounded_text(interface, "displayName", 30, errors)
    _bounded_text(interface, "shortDescription", 30, errors)
    _bounded_text(interface, "longDescription", 4000, errors, one_line=False)
    _bounded_text(interface, "developerName", 80, errors)
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not (1 <= len(prompts) <= 3):
        errors.append("plugin.json: interface.defaultPrompt must contain 1-3 prompts")
    else:
        normalized: set[str] = set()
        for prompt in prompts:
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 128 or "\n" in prompt:
                errors.append("plugin.json: each starter prompt must be one non-empty line of at most 128 characters")
                continue
            key = " ".join(prompt.split()).casefold()
            if key in normalized:
                errors.append("plugin.json: starter prompts must be unique")
            normalized.add(key)
            if "@" in prompt:
                errors.append("plugin.json: starter prompts must not contain app mentions")
    if "screenshots" in interface:
        errors.append("plugin.json: screenshots are excluded from skills-only ZIP uploads")
    for key in ("composerIcon", "logo"):
        value = interface.get(key)
        if not isinstance(value, str) or not value.startswith("./"):
            errors.append(f"plugin.json: interface.{key} must be a relative file path")
            continue
        target = package / value[2:]
        if not target.is_file():
            errors.append(f"plugin.json: interface.{key} target is missing: {value}")
            continue
        if not _safe_relative_path(value[2:]):
            errors.append(f"plugin.json: interface.{key} has an unsafe path")
            continue
        dimensions = _png_dimensions(target)
        if dimensions is None:
            errors.append(f"plugin.json: interface.{key} must reference a valid PNG")
        elif dimensions[0] != dimensions[1]:
            errors.append(f"plugin.json: interface.{key} must be square; got {dimensions}")


def _validate_skill(skill: Path, skill_id: str, errors: list[str]) -> None:
    if not skill.is_dir():
        errors.append(f"skills/{skill_id}: missing skill directory")
        return
    actual = {
        path.relative_to(skill).as_posix()
        for path in skill.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != set(REQUIRED_SKILL_FILES):
        errors.append(
            f"skills/{skill_id}: files must be exactly {list(REQUIRED_SKILL_FILES)}; "
            f"got {sorted(actual)}"
        )
    skill_path = skill / "SKILL.md"
    if skill_path.is_file():
        text = skill_path.read_text(encoding="utf-8")
        match = re.match(r"^---\nname:\s*([^\n]+)\n", text)
        if match is None or match.group(1).strip() != skill_id:
            errors.append(f"skills/{skill_id}/SKILL.md: frontmatter name must match directory")
        attributed = f"endorctl agent api --agent-id {skill_id}"
        if attributed not in text:
            errors.append(f"skills/{skill_id}/SKILL.md: missing canonical attributed CLI contract")
        if "scripts/summarize_endor_artifact.py" not in text or "$SKILL_DIR" not in text:
            errors.append(f"skills/{skill_id}/SKILL.md: missing skill-local helper resolution contract")
        if "python3 runtime/summarize_endor_artifact.py" in text:
            errors.append(f"skills/{skill_id}/SKILL.md: contains repository-relative helper command")

    metadata_path = skill / "agents" / "openai.yaml"
    metadata = _load_json(metadata_path, errors, f"skills/{skill_id}/agents/openai.yaml")
    if metadata is not None:
        if set(metadata) != {"interface", "policy"}:
            errors.append(f"skills/{skill_id}/agents/openai.yaml: only interface and policy are allowed")
        policy = metadata.get("policy")
        if policy != {"allow_implicit_invocation": True}:
            errors.append(f"skills/{skill_id}/agents/openai.yaml: implicit invocation must be enabled")
        interface = metadata.get("interface")
        required = {"display_name", "short_description", "default_prompt"}
        if not isinstance(interface, dict) or set(interface) != required:
            errors.append(f"skills/{skill_id}/agents/openai.yaml: invalid interface metadata")


def _validate_catalog_artifacts(
    root: Path,
    package: Path,
    record: dict[str, object],
    errors: list[str],
) -> None:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("manifest.json: official-directory artifacts must be a list")
        return
    expected: dict[str, dict[str, object]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
            errors.append("manifest.json: invalid official-directory artifact record")
            continue
        expected[str(artifact["path"])] = artifact
    actual = {
        path.relative_to(root).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    if set(expected) != actual:
        errors.append(
            "manifest.json: official-directory artifact set does not match package files; "
            f"missing={sorted(actual - set(expected))}, stale={sorted(set(expected) - actual)}"
        )
    for relative in sorted(actual & set(expected)):
        path = root / relative
        artifact = expected[relative]
        if artifact.get("sha256") != sha256_file(path):
            errors.append(f"manifest.json: sha256 mismatch for {relative}")
        if artifact.get("bytes") != path.stat().st_size:
            errors.append(f"manifest.json: byte count mismatch for {relative}")


def _official_package_record(
    manifest: dict[str, object],
    errors: list[str],
) -> dict[str, object] | None:
    packages = manifest.get("plugin_packages")
    if not isinstance(packages, list):
        errors.append("manifest.json: plugin_packages must be a list")
        return None
    matching = [
        package
        for package in packages
        if isinstance(package, dict)
        and package.get("host") == "codex"
        and package.get("name") == PLUGIN_NAME
        and package.get("distribution_channel", "repository") == CHANNEL
    ]
    if len(matching) != 1:
        errors.append(f"manifest.json: expected one Codex {CHANNEL!r} package record")
        return None
    record = matching[0]
    if record.get("path") != PACKAGE_PATH.as_posix():
        errors.append("manifest.json: official-directory package path is incorrect")
    if tuple(record.get("included_agents", ())) != CANONICAL_SKILL_IDS:
        errors.append("manifest.json: official-directory included_agents are not canonical")
    return record


def _report(
    root: Path,
    package: Path,
    errors: list[str],
    plugin_manifest: dict[str, object] | None,
    package_record: dict[str, object] | None,
) -> dict[str, object]:
    files = sorted(path for path in package.rglob("*") if path.is_file()) if package.is_dir() else []
    return {
        "kind": "endor.codex-directory.validation/v1",
        "validator_version": VALIDATOR_VERSION,
        "status": "passed" if not errors else "failed",
        "errors": sorted(errors),
        "package_path": PACKAGE_PATH.as_posix(),
        "package_version": str(plugin_manifest.get("version", "")) if plugin_manifest else "",
        "skill_ids": list(CANONICAL_SKILL_IDS),
        "file_count": len(files),
        "uncompressed_bytes": sum(path.stat().st_size for path in files),
        "manifest_sha256": sha256_file(_catalog_manifest_path(root)) if _catalog_manifest_path(root).is_file() else "",
        "package_record_sha256": canonical_json_digest(package_record) if package_record else "",
    }


def build_archive(
    root: Path,
    output_dir: Path,
    *,
    ai_plugins_sha: str,
    agent_kit_source_sha: str,
) -> tuple[Path, Path, Path, Path]:
    report = validate_package(root)
    if report["errors"]:
        raise ValueError("Codex directory validation failed: " + "; ".join(report["errors"]))
    _require_sha("ai-plugins", ai_plugins_sha)
    _require_sha("Agent Kit source", agent_kit_source_sha)

    package = root.resolve() / PACKAGE_PATH
    version = str(report["package_version"])
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"{PLUGIN_NAME}-codex-directory-{version}"
    archive = output_dir / f"{base}.zip"
    checksum = output_dir / f"{base}.zip.sha256"
    validation = output_dir / f"{base}.validation.json"
    attestation = output_dir / f"{base}.attestation.json"

    _write_deterministic_zip(package, archive)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        archive.unlink(missing_ok=True)
        raise ValueError(f"archive exceeds {MAX_ARCHIVE_BYTES} bytes")
    archive_sha = sha256_file(archive)
    checksum.write_text(f"{archive_sha}  {archive.name}\n", encoding="utf-8")
    validation.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    attestation_payload = {
        "kind": "endor.codex-directory.attestation/v1",
        "validator_version": VALIDATOR_VERSION,
        "status": "passed",
        "agent_kit_source_sha": agent_kit_source_sha,
        "ai_plugins_sha": ai_plugins_sha,
        "package_version": version,
        "manifest_sha256": report["manifest_sha256"],
        "package_record_sha256": report["package_record_sha256"],
        "archive": archive.name,
        "archive_sha256": archive_sha,
    }
    attestation.write_text(
        json.dumps(attestation_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return archive, checksum, validation, attestation


def _write_deterministic_zip(package: Path, archive: Path) -> None:
    files = sorted(path for path in package.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in files:
            relative = PurePosixPath(PLUGIN_NAME) / PurePosixPath(
                path.relative_to(package).as_posix()
            )
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.flag_bits |= 0x800
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _load_json(path: Path, errors: list[str], label: str) -> dict[str, object] | None:
    if not path.is_file():
        errors.append(f"{label}: missing file")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON-compatible YAML: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: expected an object")
        return None
    return value


def _catalog_manifest_path(root: Path) -> Path:
    direct = root / "manifest.json"
    if direct.is_file():
        return direct
    return root / "provenance" / "agent-kit-manifest.json"


def _bounded_text(
    interface: dict[str, object],
    key: str,
    limit: int,
    errors: list[str],
    *,
    one_line: bool = True,
) -> None:
    value = interface.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        errors.append(f"plugin.json: interface.{key} must be non-empty and at most {limit} characters")
    elif one_line and "\n" in value:
        errors.append(f"plugin.json: interface.{key} must be one line")


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def _require_sha(label: str, value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"{label} SHA must be a literal 40-character lowercase Git SHA")


def _write_report(path: Path | None, report: dict[str, object]) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--root", type=Path, default=Path("."))
    validate_parser.add_argument("--report", type=Path)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--root", type=Path, default=Path("."))
    build_parser.add_argument("--output-dir", type=Path, required=True)
    build_parser.add_argument("--ai-plugins-sha", required=True)
    build_parser.add_argument("--agent-kit-source-sha", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            report = validate_package(args.root)
            _write_report(args.report, report)
            return 0 if not report["errors"] else 1
        outputs = build_archive(
            args.root,
            args.output_dir,
            ai_plugins_sha=args.ai_plugins_sha,
            agent_kit_source_sha=args.agent_kit_source_sha,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
