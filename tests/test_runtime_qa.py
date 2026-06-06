from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import repo_root

sys.path.insert(0, str(repo_root() / "scripts"))
from run_plugin_runtime_qa import build_prompt, structured_output_schema  # noqa: E402


def test_runtime_qa_runner_writes_logs_and_closes_stdin_for_host_runs(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    calls = tmp_path / "calls.jsonl"
    fake = _fake_command(tmp_path)
    env = os.environ.copy()
    env["FAKE_QA_CALLS"] = str(calls)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "claude",
            "--host",
            "codex",
            "--host",
            "antigravity",
            "--agent",
            "sca-remediation",
            "--codex-sandbox",
            "danger-full-access",
            "--log-root",
            str(log_root),
            "--timeout",
            "5",
            "--command-override",
            f"claude={fake}",
            "--command-override",
            f"codex={fake}",
            "--command-override",
            f"antigravity={fake}",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "runtime QA logs:" in result.stdout
    summary = _load_summary(log_root)
    assert {item["host"] for item in summary["results"]} == {"claude", "codex", "antigravity"}
    assert {item["status"] for item in summary["results"]} == {"passed"}
    assert summary["task_profiles"] == {"sca-remediation": "selection-plan"}
    assert {item["task_profile"] for item in summary["results"]} == {"selection-plan"}
    assert all(Path(item["prompt_log"]).is_file() for item in summary["results"])
    assert all(Path(item["output_schema_log"]).is_file() for item in summary["results"])
    assert all(Path(item["stdout_log"]).is_file() for item in summary["results"])
    assert "tenant-a" in Path(summary["results"][0]["prompt_log"]).read_text(encoding="utf-8")
    schema = json.loads(Path(summary["results"][0]["output_schema_log"]).read_text(encoding="utf-8"))
    assert schema["required"] == [
        "summary",
        "remediation_candidates",
        "project_resolution",
        "evidence_queries",
        "selected_remediation",
        "uia_evidence",
        "risk_decision",
        "patch_plan",
        "validation",
        "change_requests",
        "tickets",
        "data_gaps",
    ]

    call_records = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    assert len(call_records) == 3
    assert all(record["stdin"] == "" for record in call_records)
    argv_by_host = {record["host"]: record["argv"] for record in call_records}
    assert "-p" in argv_by_host["claude"]
    claude_argv = argv_by_host["claude"]
    claude_prompt = build_prompt(host="claude", agent="sca-remediation", workspace=workspace, namespace="tenant-a")
    assert claude_argv[claude_argv.index("--agent") + 1] == "sca-remediation"
    assert claude_argv[claude_argv.index("--permission-mode") + 1] == "default"
    assert claude_argv.index(claude_prompt) < claude_argv.index("--add-dir")
    assert "Task profile: selection-plan" in claude_prompt
    assert "Agent task profile `selection-plan`" in claude_prompt
    assert "Use only that profile's minimal evidence" in claude_prompt
    assert "`source` must be a category" in claude_prompt
    assert "Evidence query plan:" in claude_prompt
    assert "Query VersionUpgrade/UIA candidate summaries" in claude_prompt
    assert "before any selected-candidate Finding detail" in claude_prompt
    assert "Evidence query recipes:" in claude_prompt
    assert "version-upgrade-summary" in claude_prompt
    assert "endorctl api list -r VersionUpgrade -n <namespace>" in claude_prompt
    assert "exec" in argv_by_host["codex"]
    assert "--ask-for-approval" not in argv_by_host["codex"]
    codex_argv = argv_by_host["codex"]
    codex_prompt = codex_argv[-1]
    assert "do not spawn or fork subagents" in codex_prompt
    assert codex_argv[codex_argv.index("--sandbox") + 1] == "danger-full-access"
    assert codex_argv[codex_argv.index("--output-schema") + 1].endswith("output-schema.json")
    assert "run" in argv_by_host["antigravity"]
    assert summary["codex_sandbox"] == "danger-full-access"
    assert summary["claude_permission_mode"] == "default"


def test_runtime_qa_runner_accepts_task_profile_override(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    calls = tmp_path / "calls.jsonl"
    fake = _fake_command(tmp_path)
    env = os.environ.copy()
    env["FAKE_QA_CALLS"] = str(calls)

    subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "codex",
            "--agent",
            "sca-remediation",
            "--task-profile",
            "sca-remediation=evidence-check",
            "--log-root",
            str(log_root),
            "--command-override",
            f"codex={fake}",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    summary = _load_summary(log_root)
    assert summary["task_profiles"] == {"sca-remediation": "evidence-check"}
    assert summary["results"][0]["task_profile"] == "evidence-check"
    prompt = Path(summary["results"][0]["prompt_log"]).read_text(encoding="utf-8")
    assert "Task profile: evidence-check" in prompt
    assert "Agent task profile `evidence-check`" in prompt
    assert "Use only that profile's minimal evidence" in prompt
    assert "Evidence query plan:" in prompt
    assert "Evidence query recipes:" in prompt


def test_runtime_qa_runner_records_blocked_environment_hosts(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    env = os.environ.copy()
    env["PATH"] = ""
    env.pop("CURSOR_API_KEY", None)
    env.pop("GEMINI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "gemini",
            "--host",
            "cursor",
            "--agent",
            "sca-remediation",
            "--log-root",
            str(log_root),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "gemini/sca-remediation" in result.stdout
    assert "cursor/sca-remediation" in result.stdout
    summary = _load_summary(log_root)
    assert {item["status"] for item in summary["results"]} == {"blocked"}
    assert any("CLI not found" in item["reason"] for item in summary["results"])


def test_runtime_qa_runner_marks_lint_failures_as_failed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    calls = tmp_path / "calls.jsonl"
    fake = _fake_command(tmp_path, output="not json")
    env = os.environ.copy()
    env["FAKE_QA_CALLS"] = str(calls)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "codex",
            "--agent",
            "sca-remediation",
            "--log-root",
            str(log_root),
            "--command-override",
            f"codex={fake}",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "output lint failed" in result.stdout
    summary = _load_summary(log_root)
    result_item = summary["results"][0]
    assert result_item["status"] == "failed"
    assert result_item["reason"] == "output lint failed (1 errors)"
    stderr = Path(result_item["stderr_log"]).read_text(encoding="utf-8")
    assert "sca-remediation output must include a JSON object" in stderr


def test_runtime_qa_runner_fails_on_stale_codex_plugin_cache_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    calls = tmp_path / "calls.jsonl"
    stale_path = (
        "/Users/mattbrown/.codex/plugins/cache/endor-agent-kit-local/"
        "endor-agent-kit-security-agents/0.1.0/skills/sca-remediation/SKILL.md"
    )
    fake = _fake_command(tmp_path, stderr=f"Loaded skill from {stale_path}\n")
    env = os.environ.copy()
    env["FAKE_QA_CALLS"] = str(calls)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "codex",
            "--agent",
            "sca-remediation",
            "--log-root",
            str(log_root),
            "--command-override",
            f"codex={fake}",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "stale Codex plugin cache detected" in result.stdout
    summary = _load_summary(log_root)
    result_item = summary["results"][0]
    assert result_item["status"] == "failed"
    assert result_item["reason"] == "stale Codex plugin cache detected (1 paths)"
    stderr = Path(result_item["stderr_log"]).read_text(encoding="utf-8")
    assert "legacy Endor Agent Kit package endor-agent-kit-security-agents@0.1.0" in stderr


def test_runtime_qa_runner_records_timeout_without_crashing(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_root = tmp_path / "logs"
    fake = tmp_path / "sleep_host.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        "sys.stdout.buffer.write(b'partial stdout')\n"
        "sys.stderr.buffer.write(b'partial stderr')\n"
        "sys.stdout.flush(); sys.stderr.flush()\n"
        "time.sleep(2)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--allow-live-endor-read",
            "--host",
            "codex",
            "--agent",
            "probe-droid",
            "--timeout",
            "1",
            "--log-root",
            str(log_root),
            "--command-override",
            f"codex={fake}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "timeout timed out after 1s" in result.stdout
    summary = _load_summary(log_root)
    result_item = summary["results"][0]
    assert result_item["status"] == "timeout"
    assert Path(result_item["stdout_log"]).read_text(encoding="utf-8") == "partial stdout"
    stderr = Path(result_item["stderr_log"]).read_text(encoding="utf-8")
    assert "partial stderr" in stderr
    assert "TIMEOUT after 1s" in stderr


def test_runtime_qa_runner_requires_live_read_confirmation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts" / "run_plugin_runtime_qa.py"),
            "--workspace",
            str(workspace),
            "--namespace",
            "tenant-a",
            "--host",
            "claude",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--allow-live-endor-read is required" in result.stdout


def test_runtime_qa_runner_builds_provider_neutral_schema():
    schema = structured_output_schema("sca-remediation")

    assert schema is not None
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "evidence_queries" in schema["required"]
    assert schema["properties"]["uia_evidence"]["type"] == "array"


def _fake_command(tmp_path: Path, *, output: str | None = None, stderr: str = "") -> Path:
    fake = tmp_path / "fake_host.py"
    output_payload = output or json.dumps(_valid_sca_output())
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n"
        "import json, os, sys\n"
        "argv = sys.argv[1:]\n"
        "host = 'unknown'\n"
        "if '-p' in argv:\n"
        "    host = 'claude'\n"
        "elif 'exec' in argv:\n"
        "    host = 'codex'\n"
        "elif 'run' in argv:\n"
        "    host = 'antigravity'\n"
        "record = {'host': host, 'argv': argv, 'stdin': sys.stdin.read(), 'cwd': os.getcwd()}\n"
        "with open(os.environ['FAKE_QA_CALLS'], 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(record, sort_keys=True) + '\\n')\n"
        f"sys.stderr.write({stderr!r})\n"
        f"print({output_payload!r})\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _valid_sca_output() -> dict:
    return {
        "summary": "Runtime QA fixture.",
        "remediation_candidates": [],
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture",
            "namespace": "tenant-a",
            "namespace_provenance": "current_request",
            "repo_full_name": "example/workspace",
        },
        "evidence_queries": [
            _evidence_query("VersionUpgrade", query_template_id="version-upgrade-summary"),
            _evidence_query("Finding", query_template_id="selected-finding-detail"),
        ],
        "sca_findings": [{"uuid": "finding-fixture"}],
        "selected_remediation": {
            "package": "mvn://example:demo",
            "from_version": "1.0.0",
            "to_version": "1.0.1",
            "branch_name": "remediation/sca/demo-1.0.1",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_introduced": 0,
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "findings_introduced": 0,
            }
        ],
        "risk_decision": {
            "status": "approved_low_risk",
            "source_usage_summary": "Fixture source usage is compatible.",
            "validation_requirements": ["mvn test"],
        },
        "patch_plan": [],
        "validation": [{"command": "mvn test", "status": "planned"}],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "proposed_branch": "remediation/sca/demo-1.0.1",
            }
        ],
        "tickets": [],
        "data_gaps": [],
    }


def _load_summary(log_root: Path) -> dict:
    summaries = sorted(log_root.glob("endor-agent-kit-runtime-qa-*/summary.json"))
    assert len(summaries) == 1
    return json.loads(summaries[0].read_text(encoding="utf-8"))


def _evidence_query(resource: str, *, query_template_id: str) -> dict:
    return {
        "name": f"{resource} fixture",
        "resource": resource,
        "source": "endorctl_api",
        "status": "succeeded",
        "query_template_id": query_template_id,
        "filter_summary": "fixture selector",
        "field_mask_summary": "fixture fields",
        "result_count": 1,
        "reason": "Fixture evidence.",
    }
