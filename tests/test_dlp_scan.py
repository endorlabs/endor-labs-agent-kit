from __future__ import annotations

import pytest

from conftest import repo_root
from endor_agent_kit.dlp_scan import (
    credential_findings_in_text,
    scan_catalog_credential_findings,
)
from endor_agent_kit.guardrails import check_catalog_guardrails

# Synthetic credentials are built by concatenation so no contiguous fake-token
# literal exists in this file; that exercises the regexes at runtime without
# tripping upstream secret-scanning push protection.
CREDENTIAL_SAMPLES = [
    ("-----BEGIN RSA " + "PRIVATE KEY-----", "private key block"),
    ("AKIA" + "Q" * 16, "AWS access key id"),
    ("ghp_" + "a" * 36, "GitHub token"),
    ("glpat-" + "z" * 20, "GitLab personal access token"),
    ("xoxb-" + "1" * 12 + "-" + "a" * 12, "Slack token"),
    ("sk_live_" + "0" * 24, "Stripe live secret key"),
    ("AIza" + "B" * 35, "Google API key"),
    ("npm_" + "c" * 36, "npm token"),
    ("pypi-AgEI" + "d" * 20, "PyPI token"),
    ("eyJ" + "a" * 12 + ".eyJ" + "b" * 12 + "." + "c" * 16, "JSON web token"),
    ("https://user:" + "p" * 8 + "@example.com/x", "credential in URL"),
    ("Authorization: Bearer " + "e" * 24, "authorization header credential"),
]


@pytest.mark.parametrize("value,name", CREDENTIAL_SAMPLES)
def test_credential_patterns_detect_synthetic_values(value, name):
    findings = credential_findings_in_text(f"config_value = {value}")

    assert any(found_name == name for _, found_name in findings)


def test_redaction_prose_is_not_flagged():
    prose = (
        "Redact credentials, tokens, auth headers, private keys, and secure "
        "config values from prompts, outputs, comments, tickets, and audit summaries."
    )

    assert credential_findings_in_text(prose) == []


def test_checksums_and_placeholder_examples_are_not_flagged():
    text = "\n".join(
        [
            '"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"',
            '"object_url": "https://tickets.example/SEC-4312"',
            '"approval_evidence_id": "approval-record-9f2"',
            "git@github.com:example/acme-service.git",
            "policy-123",
        ]
    )

    assert credential_findings_in_text(text) == []


def test_real_catalog_has_no_credential_findings():
    assert scan_catalog_credential_findings(repo_root()) == []


def test_check_guardrails_flags_a_planted_credential(tmp_path):
    bundle = tmp_path / "portable"
    bundle.mkdir()
    (bundle / "leak.md").write_text(
        "runtime config:\n  github_token: " + "ghp_" + "a" * 36 + "\n",
        encoding="utf-8",
    )

    errors = check_catalog_guardrails(tmp_path)

    assert any("possible hardcoded GitHub token" in error for error in errors)


def test_python_sources_are_not_scanned(tmp_path):
    # .py is excluded so test fixtures with synthetic credentials do not self-flag.
    (tmp_path / "module.py").write_text(
        "TOKEN = '" + "ghp_" + "a" * 36 + "'\n",
        encoding="utf-8",
    )

    assert scan_catalog_credential_findings(tmp_path) == []


def test_shell_hooks_are_scanned(tmp_path):
    hook = tmp_path / "plugins" / "claude" / "endor-labs-agent-kit" / "hooks" / "hook.sh"
    hook.parent.mkdir(parents=True)
    hook.write_text(
        "export GITHUB_TOKEN=ghp_" + "a" * 36 + "\n",
        encoding="utf-8",
    )

    assert scan_catalog_credential_findings(tmp_path) == [
        "plugins/claude/endor-labs-agent-kit/hooks/hook.sh:1: possible hardcoded GitHub token"
    ]
