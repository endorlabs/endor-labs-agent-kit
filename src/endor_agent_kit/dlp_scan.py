"""Mechanical DLP / credential scanning for generated catalog artifacts.

Agent Kit artifacts are prose and structured contracts that legitimately *talk
about* credentials, tokens, and auth headers (the redaction guardrails). So this
scanner matches credential *value formats*, never keywords like "token" or
"password"; that keeps false positives near zero on guardrail prose while still
catching a real key, token, private key, or credential-bearing URL that should
never ship inside a published bundle.

(Named ``dlp_scan`` rather than ``secret_scan`` so the file is not swept up by
common ``*secret*`` ignore rules and dropped from version control.)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SCANNED_SUFFIXES = (".md", ".json", ".yaml", ".yml", ".txt", ".svg", ".sh")

# Python files are excluded on purpose: test fixtures legitimately contain
# synthetic credentials used to prove this scanner works.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        ".pytest_cache",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".idea",
        ".vscode",
    }
)


@dataclass(frozen=True)
class CredentialPattern:
    """One high-confidence credential value format."""

    name: str
    pattern: re.Pattern[str]


CREDENTIAL_PATTERNS: tuple[CredentialPattern, ...] = (
    CredentialPattern("private key block", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    CredentialPattern("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    CredentialPattern("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b")),
    CredentialPattern("GitLab personal access token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20}\b")),
    CredentialPattern("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    CredentialPattern("Stripe live secret key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
    CredentialPattern("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    CredentialPattern("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    CredentialPattern("PyPI token", re.compile(r"\bpypi-AgEI[A-Za-z0-9_-]{16,}")),
    CredentialPattern(
        "JSON web token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    CredentialPattern(
        "credential in URL",
        re.compile(r"\b(?:https?|ftp)://[A-Za-z0-9._%+\-]+:[^@\s/]{3,}@"),
    ),
    CredentialPattern(
        "authorization header credential",
        re.compile(r"(?i)authorization:\s*(?:bearer|basic)\s+[A-Za-z0-9+/=._-]{16,}"),
    ),
)


def credential_findings_in_text(content: str) -> list[tuple[int, str]]:
    """Return ``(line_number, pattern_name)`` for credentials found in text."""

    findings: list[tuple[int, str]] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for credential in CREDENTIAL_PATTERNS:
            if credential.pattern.search(line):
                findings.append((line_number, credential.name))
    return findings


def scan_catalog_credential_findings(root: str | Path) -> list[str]:
    """Return credential-leak findings for scannable files under a catalog root.

    Findings name the file, line, and pattern only; the matched value is never
    echoed, so running this in CI does not leak the credential into logs.
    """

    root_path = Path(root)
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        for filename in filenames:
            if not filename.endswith(SCANNED_SUFFIXES):
                continue
            path = Path(dirpath) / filename
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relative = path.relative_to(root_path).as_posix()
            for line_number, name in credential_findings_in_text(content):
                findings.append(f"{relative}:{line_number}: possible hardcoded {name}")
    return sorted(findings)
