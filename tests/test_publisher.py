from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogAgent
from endor_agent_kit.cli import main
from endor_agent_kit.publication import HostArtifactPublication, RootCatalogAggregate
from endor_agent_kit.publisher import publish_recipe, publish_recipes

from conftest import repo_root


def _copy_agent(tmp_path: Path, agent_id: str = "dependency-decision-helper") -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _claude_code_paths(agent_id: str, *, has_setup: bool) -> set[str]:
    paths = {
        f"claude-code/{agent_id}/{agent_id}.md",
        f"claude-code/{agent_id}/README.md",
    }
    if has_setup:
        paths.add(f"claude-code/{agent_id}/endorctl-setup.md")
    return paths


def _managed_agent_paths(agent_id: str, *, has_setup: bool) -> set[str]:
    paths = {
        f"claude-managed-agents/{agent_id}/agent.yaml",
        f"claude-managed-agents/{agent_id}/environment.yaml",
        f"claude-managed-agents/{agent_id}/session-template.yaml",
        f"claude-managed-agents/{agent_id}/README.md",
    }
    if has_setup:
        paths.add(f"claude-managed-agents/{agent_id}/endorctl-setup.md")
    return paths


def test_publish_recipe_writes_customer_facing_claude_code_layout(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == (
        _claude_code_paths("dependency-decision-helper", has_setup=True)
        | _managed_agent_paths("dependency-decision-helper", has_setup=True)
        | {"manifest.json", "README.md"}
    )
    assert not (dest / "claude-code" / "dependency-decision-helper" / "standard").exists()
    assert not (dest / "claude-code" / "dependency-decision-helper" / "extended").exists()
    assert not list(dest.rglob("recipe.yaml"))
    assert not list(dest.rglob("cases.yaml"))
    assert not list(dest.rglob("system-prompt-*.md"))

    artifact = (dest / "claude-code" / "dependency-decision-helper" / "dependency-decision-helper.md").read_text()
    assert "This artifact" in artifact
    assert "mcpServers:" in artifact
    assert "disallowedTools: Bash" not in artifact.split("---", 2)[1]
    assert "Developer Edition" not in artifact
    assert "Enterprise Edition" not in artifact
    assert not (dest / "claude-code" / "dependency-decision-helper" / "developer-edition").exists()
    assert not (dest / "claude-code" / "dependency-decision-helper" / "enterprise-edition").exists()
    assert "endorctl api list" in artifact
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_publish_recipe_prepares_source_recipe_once_before_host_publication(tmp_path, monkeypatch):
    import endor_agent_kit.compilers.claude_code as claude_code_compiler
    import endor_agent_kit.compilers.claude_managed_agents as managed_agents_compiler
    import endor_agent_kit.compilers.raw as raw_compiler
    import endor_agent_kit.publisher as publisher

    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"
    prepare_calls: list[Path] = []
    real_prepare = publisher.prepare_source_recipe

    def prepare_once(recipe_path: str | Path):
        prepare_calls.append(Path(recipe_path))
        return real_prepare(recipe_path)

    def fail_if_compiler_reprepares(*_args, **_kwargs):
        raise AssertionError("publication should pass prepared recipes to compilers")

    monkeypatch.setattr(publisher, "prepare_source_recipe", prepare_once)
    monkeypatch.setattr(claude_code_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(managed_agents_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(raw_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)

    publish_recipe(recipe, dest)

    assert prepare_calls == [recipe]


def test_publish_recipes_prepares_each_source_recipe_once(tmp_path, monkeypatch):
    import endor_agent_kit.compilers.claude_code as claude_code_compiler
    import endor_agent_kit.compilers.claude_managed_agents as managed_agents_compiler
    import endor_agent_kit.compilers.raw as raw_compiler
    import endor_agent_kit.publisher as publisher

    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-decision-helper")
    vulnerability_recipe = _copy_agent(tmp_path / "vulnerability", "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"
    prepare_calls: list[Path] = []
    real_prepare = publisher.prepare_source_recipe

    def prepare_once(recipe_path: str | Path):
        prepare_calls.append(Path(recipe_path))
        return real_prepare(recipe_path)

    def fail_if_compiler_reprepares(*_args, **_kwargs):
        raise AssertionError("publication should pass prepared recipes to compilers")

    monkeypatch.setattr(publisher, "prepare_source_recipe", prepare_once)
    monkeypatch.setattr(claude_code_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(managed_agents_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(raw_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)

    publish_recipes([dependency_recipe, vulnerability_recipe], dest, prune=True)

    assert prepare_calls == [dependency_recipe, vulnerability_recipe]


def test_publish_recipe_omits_endorctl_setup_for_mcp_only_agent(tmp_path):
    recipe = _copy_agent(tmp_path, "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/vulnerability-explainer/README.md",
        "claude-code/vulnerability-explainer/vulnerability-explainer.md",
        "claude-managed-agents/vulnerability-explainer/README.md",
        "claude-managed-agents/vulnerability-explainer/agent.yaml",
        "claude-managed-agents/vulnerability-explainer/environment.yaml",
        "claude-managed-agents/vulnerability-explainer/session-template.yaml",
        "manifest.json",
        "README.md",
    }
    artifact = (dest / "claude-code" / "vulnerability-explainer" / "vulnerability-explainer.md").read_text()
    readme = (dest / "claude-code" / "vulnerability-explainer" / "README.md").read_text()
    assert "disallowedTools: Bash" in artifact
    assert "MCP-only" in artifact
    assert "endorctl-setup.md" not in readme
    assert "explain CVE-2021-44228" in readme
    assert not (
        dest
        / "claude-managed-agents"
        / "vulnerability-explainer"
        / "endorctl-setup.md"
    ).exists()
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_publish_recipe_writes_package_risk_summary_distribution(tmp_path):
    recipe = _copy_agent(tmp_path, "package-risk-summary")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    enterprise = (dest / "claude-code" / "package-risk-summary" / "package-risk-summary.md").read_text()
    enterprise_readme = (dest / "claude-code" / "package-risk-summary" / "README.md").read_text()
    assert "Endor Labs Package Risk Summary" in enterprise
    assert "mcpServers:" in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "endorctl api list" in enterprise
    assert "QuerySimilarPackages" in enterprise
    assert "summarize npm lodash version 4.17.20" in enterprise_readme
    assert (dest / "claude-code" / "package-risk-summary" / "endorctl-setup.md").is_file()
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_publish_recipe_writes_upgrade_impact_analysis_distribution(tmp_path):
    recipe = _copy_agent(tmp_path, "upgrade-impact-analysis")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    enterprise = (dest / "claude-code" / "upgrade-impact-analysis" / "upgrade-impact-analysis.md").read_text()
    managed_enterprise = (
        dest
        / "claude-managed-agents"
        / "upgrade-impact-analysis"
        / "agent.yaml"
    ).read_text()
    enterprise_readme = (dest / "claude-code" / "upgrade-impact-analysis" / "README.md").read_text()
    assert "Endor Labs Upgrade Impact Analysis" in enterprise
    assert "current_version" in enterprise
    assert "target_version" in enterprise
    assert "mcpServers:" not in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "endorctl api list" in enterprise
    assert "--resource VersionUpgrade" in enterprise
    assert "spec.upgrade_info.is_best==true" in enterprise
    assert "finding_fixing_upgrades" in enterprise
    assert "cia_results" in enterprise
    assert "show the safest upgrade path for repository <owner>/<repo> package lodash" in enterprise_readme
    assert "<project_uuid>" not in enterprise_readme
    assert "![Endor Labs Upgrade Impact Analysis architecture](architecture.svg)" in enterprise_readme
    assert "This Managed Agents artifact" in managed_enterprise
    assert "mcp_toolset" not in managed_enterprise
    assert (dest / "claude-code" / "upgrade-impact-analysis" / "architecture.svg").is_file()
    assert (dest / "claude-managed-agents" / "upgrade-impact-analysis" / "architecture.svg").is_file()
    assert (dest / "claude-code" / "upgrade-impact-analysis" / "endorctl-setup.md").is_file()
    assert (dest / "claude-managed-agents" / "upgrade-impact-analysis" / "endorctl-setup.md").is_file()
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_publish_recipe_writes_manifest_with_matching_checksums(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["generated_by"] == "endor-agent-kit"
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-decision-helper"),
        ("claude-managed-agents", "dependency-decision-helper"),
    ]
    agent = manifest["agents"][0]
    assert [edition["id"] for edition in agent["editions"]] == ["enterprise-edition"]
    assert agent["editions"][0]["path"] == "claude-code/dependency-decision-helper"

    for agent in manifest["agents"]:
        for edition in agent["editions"]:
            for artifact in edition["artifacts"]:
                path = dest / artifact["path"]
                data = path.read_bytes()
                assert artifact["sha256"] == hashlib.sha256(data).hexdigest()
                assert artifact["bytes"] == len(data)


def test_catalog_agents_return_schema_records_for_root_aggregate(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    agents = HostArtifactPublication({}).catalog_agents(dest)
    manifest = json.loads((dest / "manifest.json").read_text())

    assert agents
    assert all(isinstance(agent, CatalogAgent) for agent in agents)
    assert not any(isinstance(agent, dict) for agent in agents)
    assert [agent.to_manifest_record() for agent in agents] == manifest["agents"]
    assert RootCatalogAggregate().render_readme(agents) == (dest / "README.md").read_text()


def test_publish_recipe_is_idempotent_and_preserves_other_manifest_agents(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"
    dest.mkdir()
    (dest / "manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "generated_by": "endor-agent-kit",
            "agents": [{"id": "other-agent", "host": "claude-code", "editions": []}],
        }),
        encoding="utf-8",
    )

    publish_recipe(recipe, dest)
    first_snapshot = _snapshot(dest)
    publish_recipe(recipe, dest)
    second_snapshot = _snapshot(dest)

    assert first_snapshot == second_snapshot
    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-decision-helper"),
        ("claude-code", "other-agent"),
        ("claude-managed-agents", "dependency-decision-helper"),
    ]


def test_cli_publish_prune_removes_stale_catalog_agents(tmp_path, capsys):
    recipe = _copy_agent(tmp_path, "dependency-decision-helper")
    dest = tmp_path / "endor-labs-agent-kit"
    for host in ("claude-code", "claude-managed-agents"):
        stale_dir = dest / host / "dependency-upgrade-advisor" / "developer-edition"
        stale_dir.mkdir(parents=True)
        (stale_dir / "stale.md").write_text("stale", encoding="utf-8")
    (dest / "manifest.json").write_text(
        json.dumps({
            "schema_version": 1,
            "generated_by": "endor-agent-kit",
            "agents": [
                {"id": "dependency-upgrade-advisor", "host": "claude-code", "editions": []},
                {"id": "dependency-upgrade-advisor", "host": "claude-managed-agents", "editions": []},
            ],
        }),
        encoding="utf-8",
    )

    status = main(["publish", str(recipe), "--dest", str(dest), "--prune"])
    capsys.readouterr()

    assert status == 0
    assert not (dest / "claude-code" / "dependency-upgrade-advisor").exists()
    assert not (dest / "claude-managed-agents" / "dependency-upgrade-advisor").exists()
    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-decision-helper"),
        ("claude-managed-agents", "dependency-decision-helper"),
    ]
    assert "dependency-upgrade-advisor" not in (dest / "README.md").read_text()


def test_publish_recipe_manifest_tracks_multiple_agents(tmp_path):
    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-decision-helper")
    upgrade_recipe = _copy_agent(tmp_path / "upgrade", "upgrade-impact-analysis")
    package_recipe = _copy_agent(tmp_path / "package", "package-risk-summary")
    vulnerability_recipe = _copy_agent(tmp_path / "vulnerability", "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(dependency_recipe, dest)
    publish_recipe(upgrade_recipe, dest)
    publish_recipe(package_recipe, dest)
    publish_recipe(vulnerability_recipe, dest)

    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-decision-helper"),
        ("claude-code", "package-risk-summary"),
        ("claude-code", "upgrade-impact-analysis"),
        ("claude-code", "vulnerability-explainer"),
        ("claude-managed-agents", "dependency-decision-helper"),
        ("claude-managed-agents", "package-risk-summary"),
        ("claude-managed-agents", "upgrade-impact-analysis"),
        ("claude-managed-agents", "vulnerability-explainer"),
    ]
    package = next(
        agent
        for agent in manifest["agents"]
        if agent["host"] == "claude-code" and agent["id"] == "package-risk-summary"
    )
    package_enterprise = [edition for edition in package["editions"] if edition["id"] == "enterprise-edition"][0]
    assert package_enterprise["requires_endorctl"] == ">=1.0"
    assert "endorctl-setup.md" in {artifact["path"].split("/")[-1] for artifact in package_enterprise["artifacts"]}
    vulnerability = next(
        agent
        for agent in manifest["agents"]
        if agent["host"] == "claude-code" and agent["id"] == "vulnerability-explainer"
    )
    vulnerability_artifact = vulnerability["editions"][0]
    assert vulnerability_artifact["id"] == "developer-edition"
    assert vulnerability_artifact["path"] == "claude-code/vulnerability-explainer"
    assert vulnerability_artifact["requires_endorctl"] == ""
    assert {artifact["path"].split("/")[-1] for artifact in vulnerability_artifact["artifacts"]} == {
        "README.md",
        "vulnerability-explainer.md",
    }
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_publish_recipe_removes_stale_agent_output_before_writing(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"
    stale = dest / "claude-code" / "dependency-decision-helper" / "standard" / "old.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    publish_recipe(recipe, dest)

    assert not stale.exists()
    assert not (dest / "claude-code" / "dependency-decision-helper" / "developer-edition").exists()
    assert not (dest / "claude-code" / "dependency-decision-helper" / "enterprise-edition").exists()
    assert (dest / "claude-code" / "dependency-decision-helper" / "dependency-decision-helper.md").is_file()
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_cli_publish_writes_distribution(tmp_path, capsys):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    status = main(["publish", str(recipe), "--dest", str(dest)])
    output = capsys.readouterr().out

    assert status == 0
    assert "manifest.json" in output
    assert (dest / "manifest.json").is_file()
    assert (dest / "claude-code" / "dependency-decision-helper" / "dependency-decision-helper.md").is_file()
    assert {path.name for path in dest.iterdir()} == {"README.md", "claude-code", "claude-managed-agents", "manifest.json"}


def test_cli_publish_accepts_multiple_recipes(tmp_path, capsys):
    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-decision-helper")
    upgrade_recipe = _copy_agent(tmp_path / "upgrade", "upgrade-impact-analysis")
    package_recipe = _copy_agent(tmp_path / "package", "package-risk-summary")
    repository_recipe = _copy_agent(tmp_path / "repository", "repository-dependency-reviewer")
    vulnerability_recipe = _copy_agent(tmp_path / "vulnerability", "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    status = main([
        "publish",
        str(dependency_recipe),
        str(upgrade_recipe),
        str(package_recipe),
        str(repository_recipe),
        str(vulnerability_recipe),
        "--dest",
        str(dest),
    ])
    output = capsys.readouterr().out

    assert status == 0
    assert "dependency-decision-helper.md" in output
    assert "upgrade-impact-analysis.md" in output
    assert "package-risk-summary.md" in output
    assert "repository-dependency-reviewer.md" in output
    assert "vulnerability-explainer.md" in output
    assert "claude-managed-agents/upgrade-impact-analysis/agent.yaml" in output
    assert "claude-managed-agents/package-risk-summary/agent.yaml" in output
    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-decision-helper"),
        ("claude-code", "package-risk-summary"),
        ("claude-code", "repository-dependency-reviewer"),
        ("claude-code", "upgrade-impact-analysis"),
        ("claude-code", "vulnerability-explainer"),
        ("claude-managed-agents", "dependency-decision-helper"),
        ("claude-managed-agents", "package-risk-summary"),
        ("claude-managed-agents", "upgrade-impact-analysis"),
        ("claude-managed-agents", "vulnerability-explainer"),
    ]
    root_readme = (dest / "README.md").read_text()
    assert "## Table Of Contents" in root_readme
    assert "## Contribute An Agent" in root_readme
    assert "## Recipe Reference" in root_readme
    assert "### Ask An LLM To Install It" in root_readme
    assert "Preserve the generated agent prompt exactly" in root_readme
    assert "host_capabilities_required.read_files: true" in root_readme
    assert "Claude Code artifacts allow only `Read`, `Glob`, `Grep`, and `LS`" in root_readme
    assert "Review local dependency manifests with read-only file inspection and Endor evidence" in root_readme
    assert "@agent-repository-dependency-reviewer review this repository's dependency manifests" in root_readme
    assert "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune" in root_readme
    assert "endor-agent-kit validate-sca-output sca-output.json --gate selection-plan" in root_readme
    assert "endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md" in root_readme
    assert "endor-agent-kit lint-sca-pr-body pr-body.md" in root_readme
    assert "endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo" in root_readme
    assert "endor-agent-kit check-install --host claude-managed-agents --agent probe-droid" in root_readme
    assert "Endor Labs Upgrade Impact Analysis" in root_readme
    assert "Endor Labs Package Risk Summary" in root_readme
    assert "claude-code/upgrade-impact-analysis/" in root_readme
    assert "claude-managed-agents/upgrade-impact-analysis/" in root_readme
    assert "claude-code/package-risk-summary/" in root_readme
    assert "claude-managed-agents/package-risk-summary/" in root_readme
    assert "claude-code/repository-dependency-reviewer/" in root_readme


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
