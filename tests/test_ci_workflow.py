from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from conftest import repo_root


EVIDENCE_STEP_NAME = "Validate optional QA and backend release evidence"
QA_VAR = "AGENT_QA_ACCEPTANCE_JSON"
BACKEND_VAR = "ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON"


def publication_workflow_text() -> str:
    return (
        repo_root() / ".github" / "workflows" / "publish-ai-plugins-pr.yml"
    ).read_text(encoding="utf-8")


def evidence_step_script() -> str:
    workflow = yaml.safe_load(publication_workflow_text())
    steps = workflow["jobs"]["publish-ai-plugins-pr"]["steps"]
    step = next(item for item in steps if item.get("name") == EVIDENCE_STEP_NAME)
    return step["run"]


def _stub_workspace(tmp_path: Path) -> Path:
    """Mirror the workflow's working directory: a `.venv` python and the validator."""

    workspace = tmp_path / "endor-labs-agent-kit"
    (workspace / ".venv" / "bin").mkdir(parents=True)
    (workspace / "scripts").mkdir(parents=True)
    shim = workspace / ".venv" / "bin" / "python"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    shutil.copy(
        repo_root() / "scripts" / "validate_release_evidence.py",
        workspace / "scripts" / "validate_release_evidence.py",
    )
    shutil.copy(repo_root() / "catalog.json", workspace / "catalog.json")
    return workspace


def _release_evidence(source_commit: str) -> tuple[str, str]:
    catalog = json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": source_commit}},
    }
    backend = {
        "schema_version": "1",
        "status": "pass",
        "catalog_schema_version": 2,
        "agent_api_transport": "endorctl agent api",
        "canonical_agent_ids": [item["id"] for item in catalog["agents"]],
        "legacy_aliases": {
            alias: item["id"]
            for item in catalog["agents"]
            for alias in item.get("legacy_ids", [])
        },
        "audit_log_correlation": {
            "status": "pass",
            "observed_fields": [
                "request_id",
                "actor_type",
                "canonical_agent_id",
                "on_behalf_of",
            ],
            "canonical_agent_samples": len(catalog["agents"]),
        },
    }
    return json.dumps(qa), json.dumps(backend)


def _run_evidence_step(
    tmp_path: Path, evidence: dict[str, str]
) -> tuple[int, str, str]:
    """Run the workflow step's script the way the Actions bash shell runs it."""

    workspace = _stub_workspace(tmp_path)
    script = tmp_path / "step.sh"
    script.write_text(evidence_step_script(), encoding="utf-8")
    summary = tmp_path / "step-summary.md"
    summary.touch()
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GITHUB_SHA": "a" * 40,
        "GITHUB_STEP_SUMMARY": str(summary),
        **evidence,
    }
    completed = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        completed.returncode,
        completed.stdout + completed.stderr,
        summary.read_text(encoding="utf-8"),
    )


def test_ci_workflow_uses_source_agent_recipes():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "source/agents/*/recipe.yaml" in workflow
    assert "portable" in workflow
    assert "for recipe in agents/*/recipe.yaml" not in workflow
    assert "publish agents/*/recipe.yaml" not in workflow
    removed_plugin_path = "github-" + "co" + "pilot-plugin"
    assert removed_plugin_path not in workflow


def test_ci_workflow_runs_guardrail_conformance_check():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    # The guardrail conformance gate must stay wired into CI; this test fails if
    # the step is removed or renamed so it cannot quietly disappear.
    assert "endor-agent-kit check-guardrails --catalog-root ." in workflow


def test_ci_workflow_runs_registry_check_against_pinned_spec():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "python scripts/generate_endor_api_registry.py --check --spec source/endor-context/openapiv2.swagger.json" in workflow


def test_ci_workflow_runs_endor_context_freshness_check():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    # Offline payload validation stays blocking; the upstream freshness check
    # stays wired in but reports drift as a non-blocking warning because
    # upstream Endor releases are not failures of the commit under test.
    assert "endor-agent-kit verify-endor-context\n" in workflow
    assert "endor-agent-kit verify-endor-context --upstream" in workflow
    assert "Endor context drift" in workflow


def test_refresh_endor_context_workflow_reports_manual_freshness():
    workflow = (
        repo_root() / ".github" / "workflows" / "refresh-endor-context.yml"
    ).read_text()

    # The scheduled refresh lane must keep re-pinning provenance from upstream
    # and verifying it, but company policy requires humans to open refresh PRs.
    assert "schedule" in workflow
    assert "endor-agent-kit refresh-endor-context" in workflow
    assert "endor-agent-kit verify-endor-context --upstream" in workflow
    assert "python scripts/generate_endor_api_registry.py --check --spec source/endor-context/openapiv2.swagger.json" in workflow
    assert "source/endor-context/openapiv2.swagger.json" in workflow
    assert "Manual Endor context refresh needed" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "gh pr create" not in workflow
    assert "git push" not in workflow
    assert "endor-context-refresh" not in workflow


def test_ai_plugins_publication_validates_codex_directory_and_pins_source_provenance():
    workflow = (
        repo_root() / ".github" / "workflows" / "publish-ai-plugins-pr.yml"
    ).read_text()

    assert "provenance/agent-kit-manifest.json" in workflow
    assert "provenance/agent-kit-source.json" in workflow
    assert "build_codex_directory_submission.py validate --root ." in workflow


def test_ai_plugins_publication_gates_on_invalid_release_evidence_only() -> None:
    workflow = publication_workflow_text()
    evidence_step = workflow.split(f"- name: {EVIDENCE_STEP_NAME}", 1)[1].split(
        "- name: Regenerate catalog", 1
    )[0]
    unconfigured_branch, failure_branch = evidence_step.split(
        'if [ "$validation_status" -ne 0 ]', 1
    )

    assert "scripts/validate_release_evidence.py" in evidence_step
    assert "continue-on-error" not in evidence_step

    # Unconfigured evidence stays advisory.
    assert "Optional release evidence unavailable" in unconfigured_branch
    assert "Publication will continue" in unconfigured_branch
    assert unconfigured_branch.count("exit 0") == 1

    # Configured evidence that fails validation must fail the job, and must not
    # describe itself as advisory or continuing.
    assert "exit 1" in failure_branch
    assert "::error title=Release evidence validation failed" in failure_branch
    assert "exit 0" not in failure_branch
    assert "advisory" not in failure_branch.lower()
    assert "will continue" not in failure_branch.lower()


def test_ai_plugins_publication_pr_body_describes_release_evidence_gate() -> None:
    workflow = publication_workflow_text()
    pr_body = workflow.split("- name: Write ai-plugins PR body", 1)[1].split(
        "- name: Report dry-run diff", 1
    )[0]

    assert "validate_release_evidence.py" in pr_body
    assert "invalid evidence blocks publication" in pr_body
    assert "advisory" not in pr_body.lower()


def test_release_evidence_step_warns_and_continues_when_unconfigured(tmp_path) -> None:
    status, output, summary = _run_evidence_step(tmp_path, {})

    assert status == 0
    assert "::warning title=Optional release evidence unavailable" in output
    assert QA_VAR in output
    assert BACKEND_VAR in output
    assert "Publication will continue." in summary


def test_release_evidence_step_continues_when_only_one_variable_is_set(
    tmp_path,
) -> None:
    qa, _ = _release_evidence("a" * 40)

    status, output, summary = _run_evidence_step(tmp_path, {QA_VAR: qa})

    assert status == 0
    assert "::warning title=Optional release evidence unavailable" in output
    assert BACKEND_VAR in summary
    assert QA_VAR not in summary


def test_release_evidence_step_fails_when_configured_evidence_is_invalid(
    tmp_path,
) -> None:
    qa, backend_json = _release_evidence("a" * 40)
    backend = json.loads(backend_json)
    backend["catalog_schema_version"] = 1

    status, output, summary = _run_evidence_step(
        tmp_path, {QA_VAR: qa, BACKEND_VAR: json.dumps(backend)}
    )

    assert status != 0
    assert "::error title=Release evidence validation failed" in output
    assert "backend must accept catalog schema version 2" in output
    assert "backend must accept catalog schema version 2" in summary
    assert "blocked" in summary
    assert "Traceback" not in output


def test_release_evidence_step_fails_when_configured_evidence_is_unparseable(
    tmp_path,
) -> None:
    qa, backend = _release_evidence("a" * 40)

    status, output, _ = _run_evidence_step(
        tmp_path, {QA_VAR: "not json", BACKEND_VAR: backend}
    )

    assert status != 0
    assert "ERROR: QA acceptance is missing or invalid" in output
    assert "Traceback" not in output


def test_release_evidence_step_passes_with_valid_evidence(tmp_path) -> None:
    qa, backend = _release_evidence("a" * 40)

    status, output, summary = _run_evidence_step(
        tmp_path, {QA_VAR: qa, BACKEND_VAR: backend}
    )

    assert status == 0
    assert "OK: QA and backend release evidence" in output
    assert "validated successfully" in summary
    assert "blocked" not in summary


def test_codex_directory_submission_workflow_requires_immutable_mirror_sha():
    workflow = (
        repo_root()
        / "source"
        / "distribution"
        / "ai-plugins-workflows"
        / "build-codex-directory-submission.yml"
    ).read_text()

    assert "ai_plugins_sha" in workflow
    assert "^[0-9a-f]{40}$" in workflow
    assert "git rev-parse HEAD" in workflow
    assert "build_codex_directory_submission.py build" in workflow
    assert "publish_release_assets" in workflow
