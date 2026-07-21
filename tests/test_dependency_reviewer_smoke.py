from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code
from endor_agent_kit.publisher import publish_recipe

from conftest import repo_root
from host_artifact_bundle_contract import assert_host_bundle_files


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-reviewer"
    dst = tmp_path / "dependency-reviewer"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_reviewer_compiled_artifacts_allow_read_only_files(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    developer = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "developer-edition"
        / "dependency-reviewer-repository-review.md"
    ).read_text()
    assert (recipe.parent / "dist" / "claude-code" / "enterprise-edition").is_dir()

    for body in (developer,):
        header = body.split("---", 2)[1]
        blocked = {
            tool.strip()
            for tool in next(line for line in header.splitlines() if line.startswith("disallowedTools:"))
            .removeprefix("disallowedTools:")
            .split(",")
        }
        assert not {"Read", "Glob", "Grep", "LS"} & blocked
        assert "Bash" not in blocked
        assert {"Write", "Edit", "MultiEdit", "NotebookRead", "NotebookEdit"} <= blocked
        assert {"WebFetch", "WebSearch", "TodoWrite"} <= blocked
        assert "Dependency Reviewer" in body
        assert "host read-only file tools" in body
        assert "check_dependency_for_risks" in body
        assert "check_dependency_for_vulnerabilities" in body
        assert "get_endor_vulnerability" in body
        assert "endorctl agent api --agent-id dependency-reviewer" in body
        assert "## Repository Inspection Rules (`repository-review` only)" in body
        assert "Keep tenant/project lookups out of scope unless the request needs them" in body
        assert "retry that lookup\nwith `--traverse`" in body
        assert "unresolved_versions" in body
        assert "data_gaps" in body
        assert "Do not use prior sessions, durable memory, continuity notes" in body
        assert "cached QA reports, example repositories, or remembered project/namespace facts" in body
        assert "return `UNKNOWN` with" in body
        assert "`data_gaps`; do not claim a namespace" in body
        assert "inspect at most the" in body
        assert "first 25 selected exact direct dependencies" in body
        assert "return the final JSON after" in body
        assert "that first pass" in body
        assert "select at most five exact direct dependencies" in body
        assert "make at most one risk lookup" in body
        assert "set `risk_posture` to `UNKNOWN`" in body
        assert "`endor_mcp_package_risk_unavailable`" in body
        assert "This agent is not a repository documentation" in body
        assert "Never create, draft, or propose `CLAUDE.md`" in body
        assert "must be exactly one parseable JSON\n  object" in body


def test_dependency_reviewer_publish_writes_claude_code_codex_and_portable(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    for edition in ("developer-edition", "enterprise-edition"):
        assert_host_bundle_files(
            dest / "claude-code" / "dependency-reviewer" / edition,
            {
                "dependency-reviewer.md",
                "dependency-reviewer-package-decision.md",
                "dependency-reviewer-package-risk.md",
                "dependency-reviewer-repository-review.md",
                "README.md",
                "endorctl-setup.md",
                "architecture.svg",
            },
        )
    assert_host_bundle_files(
        dest / "portable" / "dependency-reviewer",
        {"README.md", "agent.md", "agent.manifest.json", "output-contract.md", "endorctl-setup.md"},
    )
    assert_host_bundle_files(
        dest / "codex" / "dependency-reviewer",
        {"README.md", "SKILL.md", "endorctl-setup.md"},
    )
    assert_host_bundle_files(
        dest / "gemini" / "dependency-reviewer",
        {"README.md", "SKILL.md", "dependency-reviewer.md", "endorctl-setup.md"},
    )
    assert {
        "claude-code/dependency-reviewer/developer-edition/dependency-reviewer-repository-review.md",
        "claude-code/dependency-reviewer/enterprise-edition/dependency-reviewer-package-decision.md",
        "claude-managed-agents/dependency-reviewer/agent.yaml",
        "codex/dependency-reviewer/README.md",
        "codex/dependency-reviewer/SKILL.md",
        "codex/dependency-reviewer/endorctl-setup.md",
        "gemini/dependency-reviewer/README.md",
        "gemini/dependency-reviewer/SKILL.md",
        "gemini/dependency-reviewer/dependency-reviewer.md",
        "gemini/dependency-reviewer/endorctl-setup.md",
        "portable/dependency-reviewer/README.md",
        "portable/dependency-reviewer/agent.md",
        "portable/dependency-reviewer/agent.manifest.json",
        "portable/dependency-reviewer/output-contract.md",
        "portable/dependency-reviewer/endorctl-setup.md",
        "manifest.json",
        "README.md",
        "catalog.json",
    } <= written_paths
    assert (dest / "claude-managed-agents" / "dependency-reviewer" / "agent.yaml").is_file()
    assert (
        "Review an exact package decision, package risk, or repository dependencies"
        in (dest / "README.md").read_text()
    )
    developer_readme = (
        dest / "claude-code" / "dependency-reviewer" / "developer-edition" / "README.md"
    ).read_text()
    assert "Endor MCP access through the subagent's bundled MCP server config." in developer_readme
    assert "Authenticated endorctl for the read-only API lookups" in developer_readme
    assert "endorctl agent api --agent-id dependency-reviewer" in developer_readme

    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-reviewer"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("codex", "dependency-reviewer"),
        ("gemini", "dependency-reviewer"),
        ("portable", "dependency-reviewer"),
    ]


def test_dependency_reviewer_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "dependency-reviewer" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "package-decision-safe",
        "package-decision-blocked",
        "package-risk-evidence-limited",
        "package-profile-missing-version",
        "repository-review-critical-direct-dependency",
        "repository-review-unresolved-version",
    }
    repository_cases = [
        case for case in evals["cases"] if case["input"]["task_profile"] == "repository-review"
    ]
    assert {case["expected"]["risk_posture"] for case in repository_cases} == {"CRITICAL", "UNKNOWN"}
