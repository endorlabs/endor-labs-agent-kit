from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import repo_root


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
    assert all(Path(item["prompt_log"]).is_file() for item in summary["results"])
    assert all(Path(item["stdout_log"]).is_file() for item in summary["results"])
    assert "tenant-a" in Path(summary["results"][0]["prompt_log"]).read_text(encoding="utf-8")

    call_records = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    assert len(call_records) == 3
    assert all(record["stdin"] == "" for record in call_records)
    argv_by_host = {record["host"]: record["argv"] for record in call_records}
    assert "-p" in argv_by_host["claude"]
    assert "exec" in argv_by_host["codex"]
    assert "run" in argv_by_host["antigravity"]


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


def _fake_command(tmp_path: Path) -> Path:
    fake = tmp_path / "fake_host.py"
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
        "print('fake runtime qa ok')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def _load_summary(log_root: Path) -> dict:
    summaries = sorted(log_root.glob("endor-agent-kit-runtime-qa-*/summary.json"))
    assert len(summaries) == 1
    return json.loads(summaries[0].read_text(encoding="utf-8"))
