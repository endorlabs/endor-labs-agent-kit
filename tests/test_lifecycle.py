from __future__ import annotations

import json

from conftest import repo_root

from endor_agent_kit import lifecycle
from endor_agent_kit.cli import main


def _clean_git_state(repo, *, base_ref):
    return {
        "branch": "plugin-option",
        "commit": "abc1234",
        "base_ref": base_ref,
        "remote_url": "https://github.com/endorlabs/endor-labs-agent-kit.git",
        "dirty": False,
        "dirty_paths": [],
    }


def _current_generated_state(repo, *, all_recipe_paths):
    return {
        "current": True,
        "changed_paths": [],
        "changed_path_count": 0,
        "check": "test",
        "surfaces": ["README.md"],
    }


def test_prepare_validation_request_writes_public_neutral_agent_handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "_git_state", _clean_git_state)
    monkeypatch.setattr(lifecycle, "generated_artifact_state", _current_generated_state)
    output = tmp_path / "validation-request.json"

    request = lifecycle.prepare_validation_request(
        repo_root=repo_root(),
        output=output,
        agents=["sca-remediation"],
        base_ref="origin/main",
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    agent = persisted["agents"][0]
    assert request == persisted
    assert persisted["kind"] == lifecycle.VALIDATION_REQUEST_KIND
    assert persisted["source"]["package_version"] == "2.1.0"
    assert persisted["request"]["scope"] == "explicit"
    assert persisted["request"]["publishable"] is True
    assert agent["id"] == "sca-remediation"
    assert agent["recipe"] == "source/agents/sca-remediation/recipe.yaml"
    assert agent["structured_output_contract"]["id"] == "sca-remediation"
    evidence_contract = agent["profile_contracts"]["evidence-check"]
    assert evidence_contract["output_fields"] == [
        "summary",
        "project_resolution",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    ]
    assert evidence_contract["gate_validator"] == {
        "id": "sca-remediation.read-only-profile",
        "version": "1",
    }
    assert len(evidence_contract["contract_digest"]) == 64
    assert "selection-plan" in agent["task_profiles"]
    assert agent["default_task_profile"] == "selection-plan"
    assert agent["provider_targets"] == ["antigravity", "claude", "codex", "cursor", "gemini"]
    assert "plugin:antigravity" in agent["generated_targets"]
    assert str(repo_root()) not in output.read_text(encoding="utf-8")


def test_prepare_validation_request_marks_dirty_or_stale_requests_unpublishable(tmp_path, monkeypatch):
    def dirty_git_state(repo, *, base_ref):
        state = _clean_git_state(repo, base_ref=base_ref)
        state["dirty"] = True
        state["dirty_paths"] = [" M source/agents/sca-remediation/instructions.md"]
        return state

    def stale_generated_state(repo, *, all_recipe_paths):
        return {
            "current": False,
            "changed_paths": ["codex/sca-remediation/SKILL.md"],
            "changed_path_count": 1,
            "check": "test",
            "surfaces": ["codex"],
        }

    monkeypatch.setattr(lifecycle, "_git_state", dirty_git_state)
    monkeypatch.setattr(lifecycle, "generated_artifact_state", stale_generated_state)

    request = lifecycle.prepare_validation_request(
        repo_root=repo_root(),
        output=tmp_path / "validation-request.json",
        agents=["sca-remediation"],
    )

    assert request["request"]["publishable"] is False
    assert request["generated_artifacts"]["current"] is False
    assert any("Working tree is dirty" in warning for warning in request["warnings"])
    assert any("--regenerate" in step for step in request["recommended_next_steps"])


def test_cli_lifecycle_prepare_writes_request_and_summary(tmp_path, monkeypatch, capsys):
    def fake_prepare_validation_request(**kwargs):
        kwargs["output"].write_text("{}\n", encoding="utf-8")
        return {
            "source": {
                "package": "endor-labs-agent-kit",
                "package_version": "2.1.0",
                "git": {"commit": "abc1234", "branch": "plugin-option"},
            },
            "request": {"scope": "explicit", "publishable": True},
            "generated_artifacts": {"current": True},
            "agents": [{"id": "sca-remediation"}],
            "warnings": [],
            "errors": [],
            "recommended_next_steps": [],
        }

    monkeypatch.setattr("endor_agent_kit.cli.prepare_validation_request", fake_prepare_validation_request)

    output = tmp_path / "validation-request.json"
    status = main(["lifecycle", "prepare", "--agent", "sca-remediation", "--output", str(output)])

    assert status == 0
    assert output.read_text(encoding="utf-8") == "{}\n"
    assert "validation request:" in capsys.readouterr().out
