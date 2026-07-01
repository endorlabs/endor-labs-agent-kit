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
    src = repo_root() / "source" / "agents" / "repository-dependency-reviewer"
    dst = tmp_path / "repository-dependency-reviewer"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_repository_dependency_reviewer_compiled_artifacts_allow_read_only_files(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    developer = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "developer-edition"
        / "repository-dependency-reviewer.md"
    ).read_text()
    assert not (recipe.parent / "dist" / "claude-code" / "enterprise-edition").exists()

    for body in (developer,):
        header = body.split("---", 2)[1]
        blocked = {
            tool.strip()
            for tool in next(line for line in header.splitlines() if line.startswith("disallowedTools:"))
            .removeprefix("disallowedTools:")
            .split(",")
        }
        assert not {"Read", "Glob", "Grep", "LS"} & blocked
        assert {"Bash", "Write", "Edit", "MultiEdit", "NotebookRead", "NotebookEdit"} <= blocked
        assert {"WebFetch", "WebSearch", "TodoWrite"} <= blocked
        assert "Endor Labs Repository Dependency Reviewer" in body
        assert "host read-only file tools" in body
        assert "check_dependency_for_risks" in body
        assert "check_dependency_for_vulnerabilities" in body
        assert "get_endor_vulnerability" in body
        assert "Do not use Bash" in body
        assert "Default Endor Context Scope" in body
        assert "context.type==CONTEXT_TYPE_MAIN" in body
        assert "Keep non-main counts separate" in body
        assert "retry the project lookup with `--traverse`" in body
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


def test_repository_dependency_reviewer_publish_writes_claude_code_codex_and_portable(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert_host_bundle_files(
        dest / "claude-code" / "repository-dependency-reviewer",
        {"repository-dependency-reviewer.md", "README.md"},
    )
    assert_host_bundle_files(
        dest / "portable" / "repository-dependency-reviewer",
        {"README.md", "agent.md", "agent.manifest.json", "output-contract.md"},
    )
    assert_host_bundle_files(
        dest / "codex" / "repository-dependency-reviewer",
        {"README.md", "SKILL.md"},
    )
    assert_host_bundle_files(
        dest / "gemini" / "repository-dependency-reviewer",
        {"README.md", "SKILL.md", "repository-dependency-reviewer.md"},
    )
    assert written_paths == {
        "claude-code/repository-dependency-reviewer/repository-dependency-reviewer.md",
        "claude-code/repository-dependency-reviewer/README.md",
        "codex/repository-dependency-reviewer/README.md",
        "codex/repository-dependency-reviewer/SKILL.md",
        "gemini/repository-dependency-reviewer/README.md",
        "gemini/repository-dependency-reviewer/SKILL.md",
        "gemini/repository-dependency-reviewer/repository-dependency-reviewer.md",
        "portable/repository-dependency-reviewer/README.md",
        "portable/repository-dependency-reviewer/agent.md",
        "portable/repository-dependency-reviewer/agent.manifest.json",
        "portable/repository-dependency-reviewer/output-contract.md",
        "manifest.json",
        "README.md",
        "catalog.json",
    }
    assert not (dest / "claude-managed-agents" / "repository-dependency-reviewer").exists()
    assert (
        "Review local dependency manifests with read-only file inspection and Endor evidence"
        in (dest / "README.md").read_text()
    )
    developer_readme = (
        dest / "claude-code" / "repository-dependency-reviewer" / "README.md"
    ).read_text()
    assert "Read-only access to dependency manifests in the target workspace." in developer_readme
    assert "Endor MCP tools plus Claude Code read-only file inspection" in developer_readme

    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "repository-dependency-reviewer"),
        ("codex", "repository-dependency-reviewer"),
        ("gemini", "repository-dependency-reviewer"),
        ("portable", "repository-dependency-reviewer"),
    ]


def test_repository_dependency_reviewer_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "repository-dependency-reviewer" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "npm-lockfile-vulnerable-direct-dependency",
        "maven-critical-direct-dependency",
        "unresolved-version-range",
        "clean-reviewed-repository",
    }
    postures = {case["expected"]["risk_posture"] for case in evals["cases"]}
    assert postures == {"LOW", "MODERATE", "CRITICAL", "UNKNOWN"}
