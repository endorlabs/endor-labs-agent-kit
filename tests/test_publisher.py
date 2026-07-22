from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from endor_agent_kit.catalog_schema import CatalogAgent
from endor_agent_kit.cli import main
from endor_agent_kit.publication import HostArtifactPublication, RootCatalogAggregate
from endor_agent_kit.publication.plugin_package_common import LOGO_SHA256, logo_png
from endor_agent_kit.publisher import publish_recipe, publish_recipes

from conftest import repo_root


def _copy_agent(tmp_path: Path, agent_id: str = "dependency-reviewer") -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_plugin_logo_is_canonical_endor_labs_asset():
    assert hashlib.sha256(logo_png()).hexdigest() == LOGO_SHA256


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


def _codex_paths(agent_id: str, *, has_setup: bool) -> set[str]:
    paths = {
        f"codex/{agent_id}/README.md",
        f"codex/{agent_id}/SKILL.md",
    }
    if has_setup:
        paths.add(f"codex/{agent_id}/endorctl-setup.md")
    return paths


def _gemini_paths(agent_id: str, *, has_setup: bool, has_architecture: bool = False) -> set[str]:
    paths = {
        f"gemini/{agent_id}/README.md",
        f"gemini/{agent_id}/SKILL.md",
        f"gemini/{agent_id}/{agent_id}.md",
    }
    if has_setup:
        paths.add(f"gemini/{agent_id}/endorctl-setup.md")
    if has_architecture:
        paths.add(f"gemini/{agent_id}/architecture.svg")
    return paths


def _portable_paths(
    agent_id: str,
    *,
    has_setup: bool,
    has_architecture: bool = False,
    has_actions: bool = False,
) -> set[str]:
    paths = {
        f"portable/{agent_id}/README.md",
        f"portable/{agent_id}/agent.md",
        f"portable/{agent_id}/agent.manifest.json",
        f"portable/{agent_id}/output-contract.md",
    }
    if has_setup:
        paths.add(f"portable/{agent_id}/endorctl-setup.md")
    if has_architecture:
        paths.add(f"portable/{agent_id}/architecture.svg")
    if has_actions:
        paths.add(f"portable/{agent_id}/actions.yaml")
    return paths


def test_publish_recipe_writes_customer_facing_claude_code_layout(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    expected_claude = {
        f"claude-code/dependency-reviewer/{edition}/{name}"
        for edition in ("developer-edition", "enterprise-edition")
        for name in (
            "README.md",
            "architecture.svg",
            "endorctl-setup.md",
            "dependency-reviewer.md",
            "dependency-reviewer-package-decision.md",
            "dependency-reviewer-package-risk.md",
            "dependency-reviewer-repository-review.md",
        )
    }
    assert (
        expected_claude
        | _managed_agent_paths("dependency-reviewer", has_setup=True)
        | _codex_paths("dependency-reviewer", has_setup=True)
        | _gemini_paths("dependency-reviewer", has_setup=True, has_architecture=True)
        | _portable_paths("dependency-reviewer", has_setup=True, has_architecture=True)
        | {"manifest.json", "README.md", "catalog.json"}
    ) <= written_paths
    runtime_helper = "runtime/summarize_endor_artifact.py"
    assert {
        f"claude-code/dependency-reviewer/developer-edition/{runtime_helper}",
        f"claude-code/dependency-reviewer/enterprise-edition/{runtime_helper}",
        f"claude-managed-agents/dependency-reviewer/{runtime_helper}",
        f"codex/dependency-reviewer/{runtime_helper}",
        f"gemini/dependency-reviewer/{runtime_helper}",
        f"portable/dependency-reviewer/{runtime_helper}",
    } <= written_paths
    assert not (dest / "claude-code" / "dependency-reviewer" / "standard").exists()
    assert not (dest / "claude-code" / "dependency-reviewer" / "extended").exists()
    assert not list(dest.rglob("recipe.yaml"))
    assert not list(dest.rglob("cases.yaml"))
    assert not list(dest.rglob("system-prompt-*.md"))

    artifact = (
        dest
        / "claude-code"
        / "dependency-reviewer"
        / "enterprise-edition"
        / "dependency-reviewer.md"
    ).read_text()
    assert "Dependency Reviewer" in artifact
    assert "mcpServers:" in artifact
    assert "disallowedTools: Bash" not in artifact.split("---", 2)[1]
    assert (dest / "claude-code" / "dependency-reviewer" / "developer-edition").is_dir()
    assert (dest / "claude-code" / "dependency-reviewer" / "enterprise-edition").is_dir()
    assert "endorctl agent api --agent-id dependency-reviewer list" in artifact
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipe_catalogues_named_claude_code_profile_variants(tmp_path):
    recipe = _copy_agent(tmp_path, "sca-remediation")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    agent_dir = dest / "claude-code" / "sca-remediation"
    expected_profiles = {"resolve-scope", "evidence-check", "selection-plan"}
    assert {
        path.stem.removeprefix("sca-remediation-")
        for path in agent_dir.glob("sca-remediation-*.md")
    } == expected_profiles

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    claude_agent = next(
        agent
        for agent in manifest["agents"]
        if agent["id"] == "sca-remediation" and agent["host"] == "claude-code"
    )
    profile_artifacts = {
        artifact["profile_id"]: Path(artifact["path"]).name
        for artifact in claude_agent["editions"][0]["artifacts"]
        if "profile_id" in artifact
    }
    assert profile_artifacts == {
        profile_id: f"sca-remediation-{profile_id}.md"
        for profile_id in expected_profiles
    }
    for artifact in claude_agent["editions"][0]["artifacts"]:
        if "profile_id" not in artifact:
            continue
        assert len(artifact["profile_contract_digest"]) == 64
        assert artifact["profile_gate_validator"]["version"] == "1"


def test_publish_recipe_emits_identical_inert_evidence_plans_for_every_host(tmp_path):
    recipe = _copy_agent(tmp_path, "sca-remediation")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    plan_paths = sorted(dest.glob("*/sca-remediation/evidence-plans/evidence-check.json"))
    assert {path.parts[-4] for path in plan_paths} == {
        "claude-code",
        "codex",
        "gemini",
        "portable",
    }
    assert len({path.read_bytes() for path in plan_paths}) == 1
    payload = json.loads(plan_paths[0].read_text(encoding="utf-8"))
    assert payload["execution"] == {
        "host_adapter_required": True,
        "mode": "prompt_fallback",
        "prompt_recipes_exposed": True,
    }

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    plan_artifacts = [
        artifact
        for agent in manifest["agents"]
        if agent["id"] == "sca-remediation"
        for edition in agent["editions"]
        for artifact in edition["artifacts"]
        if artifact["path"].endswith("/evidence-plans/evidence-check.json")
    ]
    assert len(plan_artifacts) == 4
    assert {artifact["evidence_execution_mode"] for artifact in plan_artifacts} == {
        "prompt_fallback"
    }
    assert {artifact["evidence_plan_executable"] for artifact in plan_artifacts} == {False}
    assert {
        artifact["evidence_plan_digest"] for artifact in plan_artifacts
    } == {payload["provenance"]["plan_digest"]}


def test_publish_recipe_emits_verifiable_profile_contracts_for_every_host(tmp_path):
    recipe = _copy_agent(tmp_path, "sca-remediation")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    contract_paths = sorted(
        dest.glob("*/sca-remediation/profile-contracts/evidence-check.json")
    )
    assert {path.parts[-4] for path in contract_paths} == {
        "claude-code",
        "codex",
        "gemini",
        "portable",
    }
    assert len({path.read_bytes() for path in contract_paths}) == 1
    payload = json.loads(contract_paths[0].read_text(encoding="utf-8"))
    assert payload["agent_id"] == "sca-remediation"
    assert payload["profile_id"] == "evidence-check"

    plan = json.loads(
        next(
            dest.glob(
                "*/sca-remediation/evidence-plans/evidence-check.json"
            )
        ).read_text(encoding="utf-8")
    )
    assert (
        payload["contract_digest"]
        == plan["provenance"]["profile_contract_digest"]
    )

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    contract_artifacts = [
        artifact
        for agent in manifest["agents"]
        if agent["id"] == "sca-remediation"
        for edition in agent["editions"]
        for artifact in edition["artifacts"]
        if artifact["path"].endswith(
            "/profile-contracts/evidence-check.json"
        )
    ]
    assert len(contract_artifacts) == 4
    assert {
        artifact["profile_contract_digest"]
        for artifact in contract_artifacts
    } == {payload["contract_digest"]}


def test_claude_plugin_packages_include_named_profile_agents(tmp_path):
    recipe = _copy_agent(tmp_path, "sca-remediation")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipes([recipe], dest, include_plugins=True)

    for package_name in ("endor-labs-agent-kit", "ai-plugins"):
        agents_dir = dest / "plugins" / "claude" / package_name / "agents"
        for profile_id in ("resolve-scope", "evidence-check", "selection-plan"):
            variant = agents_dir / f"sca-remediation-{profile_id}.md"
            assert variant.is_file()
            assert f"name: sca-remediation-{profile_id}" in variant.read_text(encoding="utf-8")


def test_publish_recipe_prepares_source_recipe_once_before_host_publication(tmp_path, monkeypatch):
    import endor_agent_kit.compilers.claude_code as claude_code_compiler
    import endor_agent_kit.compilers.claude_managed_agents as managed_agents_compiler
    import endor_agent_kit.compilers.portable as portable_compiler
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
    monkeypatch.setattr(portable_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(raw_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)

    publish_recipe(recipe, dest)

    assert prepare_calls == [recipe]


def test_publish_recipes_prepares_each_source_recipe_once(tmp_path, monkeypatch):
    import endor_agent_kit.compilers.claude_code as claude_code_compiler
    import endor_agent_kit.compilers.claude_managed_agents as managed_agents_compiler
    import endor_agent_kit.compilers.portable as portable_compiler
    import endor_agent_kit.compilers.raw as raw_compiler
    import endor_agent_kit.publisher as publisher

    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-reviewer")
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
    monkeypatch.setattr(portable_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)
    monkeypatch.setattr(raw_compiler, "prepare_source_recipe", fail_if_compiler_reprepares)

    publish_recipes([dependency_recipe, vulnerability_recipe], dest, prune=True)

    assert prepare_calls == [dependency_recipe, vulnerability_recipe]


def test_publish_recipe_adds_endorctl_setup_for_vulnerability_explainer(tmp_path):
    recipe = _copy_agent(tmp_path, "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    contract_and_plan_paths = {
        f"{host}/vulnerability-explainer/profile-contracts/{profile_id}.json"
        for host in ("claude-code", "claude-managed-agents", "codex", "gemini", "portable")
        for profile_id in ("explain", "evidence-check")
    } | {
        f"{host}/vulnerability-explainer/evidence-plans/explain.json"
        for host in ("claude-code", "claude-managed-agents", "codex", "gemini", "portable")
    }
    runtime_paths = {
        f"{host}/vulnerability-explainer/runtime/summarize_endor_artifact.py"
        for host in ("claude-code", "claude-managed-agents", "codex", "gemini", "portable")
    }
    assert written_paths == {
        "claude-code/vulnerability-explainer/README.md",
        "claude-code/vulnerability-explainer/endorctl-setup.md",
        "claude-code/vulnerability-explainer/vulnerability-explainer.md",
        "claude-managed-agents/vulnerability-explainer/README.md",
        "claude-managed-agents/vulnerability-explainer/agent.yaml",
        "claude-managed-agents/vulnerability-explainer/endorctl-setup.md",
        "claude-managed-agents/vulnerability-explainer/environment.yaml",
        "claude-managed-agents/vulnerability-explainer/session-template.yaml",
        "manifest.json",
        "README.md",
        "catalog.json",
    } | _codex_paths("vulnerability-explainer", has_setup=True) | _gemini_paths(
        "vulnerability-explainer",
        has_setup=True,
    ) | _portable_paths("vulnerability-explainer", has_setup=True) | contract_and_plan_paths | runtime_paths
    artifact = (dest / "claude-code" / "vulnerability-explainer" / "vulnerability-explainer.md").read_text()
    readme = (dest / "claude-code" / "vulnerability-explainer" / "README.md").read_text()
    assert "disallowedTools: Bash" not in artifact
    assert "endorctl agent api --agent-id vulnerability-explainer" in artifact
    assert "endorctl-setup.md" in readme
    assert "explain CVE-2021-44228" in readme
    assert (
        dest
        / "claude-managed-agents"
        / "vulnerability-explainer"
        / "endorctl-setup.md"
    ).exists()
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipe_writes_package_risk_summary_distribution(tmp_path):
    recipe = _copy_agent(tmp_path, "dependency-reviewer")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    enterprise_dir = dest / "claude-code" / "dependency-reviewer" / "enterprise-edition"
    enterprise = (enterprise_dir / "dependency-reviewer-package-risk.md").read_text()
    enterprise_readme = (enterprise_dir / "README.md").read_text()
    assert "Dependency Reviewer" in enterprise
    assert "mcpServers:" in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "endorctl agent api --agent-id dependency-reviewer list" in enterprise
    assert "QuerySimilarPackages" not in enterprise
    assert "exact package decision" in enterprise_readme
    for profile in ("package-decision", "package-risk", "repository-review"):
        assert (enterprise_dir / f"dependency-reviewer-{profile}.md").is_file()
    assert (enterprise_dir / "endorctl-setup.md").is_file()
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipe_writes_oss_upgrade_investigator_distribution(tmp_path):
    recipe = _copy_agent(tmp_path, "oss-upgrade-investigator")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    enterprise = (dest / "claude-code" / "oss-upgrade-investigator" / "oss-upgrade-investigator.md").read_text()
    managed_enterprise = (
        dest
        / "claude-managed-agents"
        / "oss-upgrade-investigator"
        / "agent.yaml"
    ).read_text()
    enterprise_readme = (dest / "claude-code" / "oss-upgrade-investigator" / "README.md").read_text()
    assert "OSS Upgrade Investigator" in enterprise
    assert "current_version" in enterprise
    assert "target_version" in enterprise
    assert "mcpServers:" not in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "endorctl agent api --agent-id oss-upgrade-investigator list" in enterprise
    assert "--resource VersionUpgrade" in enterprise
    assert "spec.upgrade_info.is_best==true" in enterprise
    assert "finding_fixing_upgrades" in enterprise
    assert "cia_results" in enterprise
    assert "show the safest upgrade path for repository <owner>/<repo> package lodash" in enterprise_readme
    assert "<project_uuid>" not in enterprise_readme
    assert "![OSS Upgrade Investigator architecture](architecture.svg)" in enterprise_readme
    assert "This Managed Agents artifact" in managed_enterprise
    assert "mcp_toolset" not in managed_enterprise
    assert (dest / "claude-code" / "oss-upgrade-investigator" / "architecture.svg").is_file()
    assert (dest / "claude-managed-agents" / "oss-upgrade-investigator" / "architecture.svg").is_file()
    assert (dest / "claude-code" / "oss-upgrade-investigator" / "endorctl-setup.md").is_file()
    assert (dest / "claude-managed-agents" / "oss-upgrade-investigator" / "endorctl-setup.md").is_file()
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipe_writes_manifest_with_matching_checksums(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["generated_by"] == "endor-agent-kit"
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-reviewer"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("codex", "dependency-reviewer"),
        ("gemini", "dependency-reviewer"),
        ("portable", "dependency-reviewer"),
    ]
    agent = manifest["agents"][0]
    assert [edition["id"] for edition in agent["editions"]] == [
        "developer-edition",
        "enterprise-edition",
    ]
    assert agent["editions"][0]["path"] == "claude-code/dependency-reviewer/developer-edition"

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
        ("claude-code", "dependency-reviewer"),
        ("claude-code", "other-agent"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("codex", "dependency-reviewer"),
        ("gemini", "dependency-reviewer"),
        ("portable", "dependency-reviewer"),
    ]


def test_cli_publish_prune_removes_stale_catalog_agents(tmp_path, capsys):
    recipe = _copy_agent(tmp_path, "dependency-reviewer")
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
        ("claude-code", "dependency-reviewer"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("codex", "dependency-reviewer"),
        ("gemini", "dependency-reviewer"),
        ("portable", "dependency-reviewer"),
    ]
    assert "dependency-upgrade-advisor" not in (dest / "README.md").read_text()


def test_publish_recipe_manifest_tracks_multiple_agents(tmp_path):
    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-reviewer")
    upgrade_recipe = _copy_agent(tmp_path / "upgrade", "oss-upgrade-investigator")
    vulnerability_recipe = _copy_agent(tmp_path / "vulnerability", "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(dependency_recipe, dest)
    publish_recipe(upgrade_recipe, dest)
    publish_recipe(vulnerability_recipe, dest)

    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-reviewer"),
        ("claude-code", "oss-upgrade-investigator"),
        ("claude-code", "vulnerability-explainer"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("claude-managed-agents", "oss-upgrade-investigator"),
        ("claude-managed-agents", "vulnerability-explainer"),
        ("codex", "dependency-reviewer"),
        ("codex", "oss-upgrade-investigator"),
        ("codex", "vulnerability-explainer"),
        ("gemini", "dependency-reviewer"),
        ("gemini", "oss-upgrade-investigator"),
        ("gemini", "vulnerability-explainer"),
        ("portable", "dependency-reviewer"),
        ("portable", "oss-upgrade-investigator"),
        ("portable", "vulnerability-explainer"),
    ]
    dependency = next(
        agent
        for agent in manifest["agents"]
        if agent["host"] == "claude-code" and agent["id"] == "dependency-reviewer"
    )
    dependency_enterprise = [edition for edition in dependency["editions"] if edition["id"] == "enterprise-edition"][0]
    assert dependency_enterprise["requires_endorctl"] == ">=1.0.0"
    assert "endorctl-setup.md" in {artifact["path"].split("/")[-1] for artifact in dependency_enterprise["artifacts"]}
    vulnerability = next(
        agent
        for agent in manifest["agents"]
        if agent["host"] == "claude-code" and agent["id"] == "vulnerability-explainer"
    )
    vulnerability_artifact = vulnerability["editions"][0]
    assert vulnerability_artifact["id"] == "developer-edition"
    assert vulnerability_artifact["path"] == "claude-code/vulnerability-explainer"
    assert vulnerability_artifact["requires_endorctl"] == ">=1.0.0"
    assert vulnerability["requires_endorctl"] == ">=1.0.0"
    assert {artifact["path"].split("/")[-1] for artifact in vulnerability_artifact["artifacts"]} == {
        "README.md",
        "endorctl-setup.md",
        "evidence-check.json",
        "explain.json",
        "summarize_endor_artifact.py",
        "vulnerability-explainer.md",
    }
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipe_removes_stale_agent_output_before_writing(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"
    stale = dest / "claude-code" / "dependency-reviewer" / "standard" / "old.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    publish_recipe(recipe, dest)

    assert not stale.exists()
    assert (dest / "claude-code" / "dependency-reviewer" / "developer-edition").is_dir()
    assert (dest / "claude-code" / "dependency-reviewer" / "enterprise-edition").is_dir()
    assert (
        dest
        / "claude-code"
        / "dependency-reviewer"
        / "enterprise-edition"
        / "dependency-reviewer.md"
    ).is_file()
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_cli_publish_writes_distribution(tmp_path, capsys):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    status = main(["publish", str(recipe), "--dest", str(dest)])
    output = capsys.readouterr().out

    assert status == 0
    assert "manifest.json" in output
    assert (dest / "manifest.json").is_file()
    assert (
        dest
        / "claude-code"
        / "dependency-reviewer"
        / "enterprise-edition"
        / "dependency-reviewer.md"
    ).is_file()
    assert (dest / "portable" / "dependency-reviewer" / "agent.md").is_file()
    assert {path.name for path in dest.iterdir()} == {
        "README.md",
        "catalog.json",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "gemini",
        "manifest.json",
        "portable",
    }


def test_publish_recipes_with_plugins_writes_all_generated_plugin_packages(tmp_path):
    canonical_agent_ids = (
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
    claude_agent_ids = canonical_agent_ids
    codex_agent_ids = canonical_agent_ids
    gemini_agent_ids = codex_agent_ids
    antigravity_agent_ids = gemini_agent_ids
    cursor_agent_ids = codex_agent_ids
    cursor_sdk_agent_ids = cursor_agent_ids
    cursor_architecture_agent_ids = {
        "ai-sast-remediation",
        "cicd-posture",
        "troubleshooting",
        "findings-browser",
        "malware-responder",
        "configuration-automation",
        "remediation-planning",
        "sca-remediation",
        "oss-upgrade-investigator",
    }
    recipes = [
        _copy_agent(tmp_path / agent_id, agent_id)
        for agent_id in claude_agent_ids
    ]
    dest = tmp_path / "endor-labs-agent-kit"
    existing_creator_skill = dest / "skills" / "create-endor-labs-agent" / "SKILL.md"
    existing_creator_skill.parent.mkdir(parents=True)
    existing_creator_skill.write_text("# existing creator skill\n")
    stale_skill = dest / "skills" / "retired-agent" / "SKILL.md"
    stale_skill.parent.mkdir(parents=True)
    stale_skill.write_text("<!-- endor_agent_kit_managed=true agent_id=retired-agent host=cursor -->\n")
    stale_agent = dest / "agents" / "endor-retired-agent.md"
    stale_agent.parent.mkdir(parents=True)
    stale_agent.write_text("<!-- endor_agent_kit_managed=true agent_id=retired-agent host=cursor -->\n")
    stale_root_gemini_manifest = dest / "gemini-extension.json"
    stale_root_gemini_manifest.write_text("{}\n", encoding="utf-8")

    written = publish_recipes(recipes, dest, include_plugins=True)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert "plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json" in written_paths
    assert ".agents/plugins/marketplace.json" in written_paths
    assert "plugins/codex/.agents/plugins/marketplace.json" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/agents/endor-agent-kit-setup-agent.toml" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/runtime/summarize_endor_artifact.py" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/assets/logo.png" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/hooks.json" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/check-dep-install.sh" in written_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/check-manifest-edit.sh" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json" in written_paths
    assert ".claude-plugin/marketplace.json" in written_paths
    assert "plugins/claude/.claude-plugin/marketplace.json" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/assets/logo.png" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/runtime/summarize_endor_artifact.py" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/hooks.json" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/check-dep-install.sh" in written_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/check-manifest-edit.sh" in written_paths
    assert "plugins/claude/ai-plugins/.claude-plugin/plugin.json" in written_paths
    assert "plugins/claude/ai-plugins/skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "plugins/claude/ai-plugins/assets/logo.png" in written_paths
    assert "plugins/claude/ai-plugins/runtime/summarize_endor_artifact.py" in written_paths
    assert "plugins/claude/ai-plugins/hooks/hooks.json" not in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/gemini-extension.json" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/GEMINI.md" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/assets/logo.png" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/runtime/summarize_endor_artifact.py" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/hooks/hooks.json" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/hooks/check-dep-install.sh" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit/hooks/check-manifest-edit.sh" in written_paths
    assert "plugins/gemini/endor-labs-agent-kit.zip" not in written_paths
    assert not (dest / "plugins" / "gemini" / "endor-labs-agent-kit.zip").exists()
    assert "plugins/antigravity/endor-labs-agent-kit/plugin.json" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/assets/logo.png" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/runtime/summarize_endor_artifact.py" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/hooks.json" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/hooks/check-dep-install.sh" in written_paths
    assert "plugins/antigravity/endor-labs-agent-kit/hooks/check-manifest-edit.sh" in written_paths
    assert ".cursor-plugin/plugin.json" in written_paths
    assert ".cursor-plugin/marketplace.json" in written_paths
    assert "runtime/summarize_endor_artifact.py" in written_paths
    assert "hooks/hooks.json" in written_paths
    assert "hooks/suggest-endor-tools.sh" in written_paths
    assert "hooks/check-dep-install.sh" in written_paths
    assert "hooks/check-manifest-edit.sh" in written_paths
    assert "skills/endor-agent-kit-setup/SKILL.md" in written_paths
    assert "agents/endor-agent-kit-setup-agent.md" in written_paths
    assert "cursor-sdk/README.md" in written_paths
    assert "cursor-sdk/requirements.txt" in written_paths
    assert "cursor-sdk/run_cursor_agent.py" in written_paths
    assert "cursor-sdk/runtime/summarize_endor_artifact.py" in written_paths
    assert "cursor-sdk/agent_definitions.json" in written_paths
    assert "cursor-sdk/agents/endor-agent-kit-setup-agent.md" in written_paths
    assert "assets/logo.png" in written_paths
    assert ".mcp.json" in written_paths
    assert "GEMINI.md" in written_paths
    assert "gemini-extension.json" not in written_paths
    assert not (dest / "gemini-extension.json").exists()
    assert existing_creator_skill.read_text() == "# existing creator skill\n"
    assert not stale_skill.exists()
    assert not stale_agent.exists()
    assert not list(dest.rglob("logo.svg"))
    canonical_logo = logo_png()
    for logo_path in dest.rglob("logo.png"):
        assert logo_path.read_bytes() == canonical_logo

    for agent_id in codex_agent_ids:
        assert f"plugins/codex/endor-labs-agent-kit/skills/{agent_id}/SKILL.md" in written_paths
        agent_name = (
            f"{agent_id}-agent"
            if agent_id.startswith("endor-")
            else f"endor-{agent_id}-agent"
        )
        assert f"plugins/codex/endor-labs-agent-kit/agents/{agent_name}.toml" in written_paths
    for agent_id in claude_agent_ids:
        assert f"plugins/claude/endor-labs-agent-kit/agents/{agent_id}.md" in written_paths
        assert f"plugins/claude/ai-plugins/agents/{agent_id}.md" in written_paths
    for agent_id in gemini_agent_ids:
        assert f"plugins/gemini/endor-labs-agent-kit/skills/{agent_id}/SKILL.md" in written_paths
        assert f"plugins/gemini/endor-labs-agent-kit/agents/{agent_id}.md" in written_paths
    for agent_id in antigravity_agent_ids:
        assert f"plugins/antigravity/endor-labs-agent-kit/skills/{agent_id}/SKILL.md" in written_paths
        assert f"plugins/antigravity/endor-labs-agent-kit/agents/{agent_id}.md" in written_paths
    for agent_id in cursor_agent_ids:
        assert f"skills/{agent_id}/SKILL.md" in written_paths
        if agent_id in cursor_architecture_agent_ids:
            assert f"skills/{agent_id}/architecture.svg" in written_paths
        cursor_agent_name = (
            f"{agent_id}-agent"
            if agent_id.startswith("endor-")
            else f"endor-{agent_id}-agent"
        )
        assert f"agents/{cursor_agent_name}.md" in written_paths
        assert f"cursor-sdk/agents/{cursor_agent_name}.md" in written_paths

    plugin_manifest = json.loads(
        (dest / "plugins" / "codex" / "endor-labs-agent-kit" / ".codex-plugin" / "plugin.json").read_text()
    )
    codex_plugin_readme = (
        dest / "plugins" / "codex" / "endor-labs-agent-kit" / "README.md"
    ).read_text()
    codex_setup_skill = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    codex_setup_agent = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "agents"
        / "endor-agent-kit-setup-agent.toml"
    ).read_text()
    codex_installer_path = "plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py"
    assert f"python {codex_installer_path}" in codex_plugin_readme
    assert codex_installer_path in codex_setup_skill
    assert 'python "$ENDOR_CODEX_INSTALLER"' in codex_setup_skill
    assert codex_installer_path in codex_setup_agent
    assert "ENDOR_CODEX_INSTALLER" in codex_setup_agent
    for codex_setup_text in (codex_plugin_readme, codex_setup_skill, codex_setup_agent):
        assert "python scripts/install_codex_agents.py" not in codex_setup_text
    assert "## Start Here" in codex_plugin_readme
    assert "Agent installer" in codex_plugin_readme
    assert "sync generated artifacts to `ai-plugins`" in codex_plugin_readme
    assert "Content releases require a package version bump" in codex_plugin_readme
    assert "endor-agent-kit-setup-agent" in codex_plugin_readme
    plugins_readme = (dest / "plugins" / "README.md").read_text()
    assert "github.com/endorlabs/endor-labs-agent-kit/blob/main/docs/getting-started.md" in plugins_readme
    assert "github.com/endorlabs/endor-labs-agent-kit/blob/main/docs/maintainer-guide.md" in plugins_readme
    assert plugin_manifest["name"] == "endor-labs-agent-kit"
    assert plugin_manifest["version"] == "2.1.0"
    assert plugin_manifest["skills"] == "./skills/"
    assert plugin_manifest["hooks"] == "./hooks/hooks.json"
    assert "agents" not in plugin_manifest
    assert plugin_manifest["interface"]["displayName"] == "Endor Labs Agent Kit"
    assert plugin_manifest["interface"]["defaultPrompt"] == [
        "Set up Endor Agent Kit for this machine.",
        "Triage AI SAST findings for this repository.",
        "Find the safest SCA remediation path.",
    ]
    assert "license" not in plugin_manifest
    claude_plugin_manifest = json.loads(
        (dest / "plugins" / "claude" / "endor-labs-agent-kit" / ".claude-plugin" / "plugin.json").read_text()
    )
    assert claude_plugin_manifest["name"] == "endor-labs-agent-kit"
    assert claude_plugin_manifest["version"] == "2.1.0"
    assert claude_plugin_manifest["displayName"] == "Endor Labs Agent Kit"
    assert "agents" not in claude_plugin_manifest
    assert "skills" not in claude_plugin_manifest
    assert "license" not in claude_plugin_manifest
    assert "mcpServers" not in claude_plugin_manifest
    assert "hooks" not in claude_plugin_manifest
    claude_hooks = json.loads(
        (dest / "plugins" / "claude" / "endor-labs-agent-kit" / "hooks" / "hooks.json").read_text()
    )
    assert set(claude_hooks["hooks"]) == {"UserPromptSubmit", "PostToolUse"}
    hook_scripts = {
        "suggest-endor-tools.sh",
        "check-dep-install.sh",
        "check-manifest-edit.sh",
    }
    assert {
        path.name
        for path in (dest / "plugins" / "claude" / "endor-labs-agent-kit" / "hooks").glob("*.sh")
    } == hook_scripts
    for script in hook_scripts:
        hook_text = (
            dest / "plugins" / "claude" / "endor-labs-agent-kit" / "hooks" / script
        ).read_text()
        assert "endor_agent_kit_managed=true" in hook_text
        assert "hookSpecificOutput" in hook_text
        assert "additionalContext" in hook_text
    assert not (dest / "plugins" / "claude" / "ai-plugins" / "hooks").exists()
    codex_hooks = json.loads(
        (dest / "plugins" / "codex" / "endor-labs-agent-kit" / "hooks" / "hooks.json").read_text()
    )
    assert set(codex_hooks["hooks"]) == {"UserPromptSubmit", "PostToolUse"}
    assert "${PLUGIN_ROOT}/hooks/suggest-endor-tools.sh" in json.dumps(codex_hooks)
    cursor_hooks = json.loads((dest / "hooks" / "hooks.json").read_text())
    assert set(cursor_hooks["hooks"]) == {
        "beforeSubmitPrompt",
        "beforeShellExecution",
        "afterFileEdit",
    }
    assert "beforeSubmitPrompt" in json.dumps(cursor_hooks)
    gemini_hooks = json.loads(
        (dest / "plugins" / "gemini" / "endor-labs-agent-kit" / "hooks" / "hooks.json").read_text()
    )
    assert set(gemini_hooks["hooks"]) == {"BeforeAgent", "BeforeTool", "AfterTool"}
    assert "run_shell_command" in json.dumps(gemini_hooks)
    antigravity_hooks = json.loads(
        (dest / "plugins" / "antigravity" / "endor-labs-agent-kit" / "hooks.json").read_text()
    )
    assert set(antigravity_hooks["hooks"]) == {"PreInvocation", "PreToolUse", "PostToolUse"}
    assert "run_command" in json.dumps(antigravity_hooks)
    claude_discovery_terms = {
        "agentic remediation",
        "SAST remediation",
        "agentic AppSec",
        "AppSec",
        "OSS Upgrade Investigator",
    }
    assert claude_discovery_terms <= set(claude_plugin_manifest["keywords"])
    legacy_claude_plugin_manifest = json.loads(
        (dest / "plugins" / "claude" / "ai-plugins" / ".claude-plugin" / "plugin.json").read_text()
    )
    assert legacy_claude_plugin_manifest["name"] == "ai-plugins"
    assert legacy_claude_plugin_manifest["displayName"] == "Endor Labs AI Plugins (Legacy)"
    assert legacy_claude_plugin_manifest["version"] == "1.2.0"
    assert "agents" not in legacy_claude_plugin_manifest
    assert "skills" not in legacy_claude_plugin_manifest
    assert "license" not in legacy_claude_plugin_manifest
    assert "mcpServers" not in legacy_claude_plugin_manifest
    assert "hooks" not in legacy_claude_plugin_manifest
    assert claude_discovery_terms <= set(legacy_claude_plugin_manifest["keywords"])
    gemini_plugin_manifest = json.loads(
        (dest / "plugins" / "gemini" / "endor-labs-agent-kit" / "gemini-extension.json").read_text()
    )
    assert gemini_plugin_manifest == {
        "contextFileName": "GEMINI.md",
        "description": "Endor Labs workflow skills and subagents for Gemini CLI.",
        "name": "endor-labs-agent-kit",
        "version": gemini_plugin_manifest["version"],
    }
    assert "mcpServers" not in gemini_plugin_manifest
    assert "settings" not in gemini_plugin_manifest
    assert "license" not in gemini_plugin_manifest
    root_mcp_config = json.loads((dest / ".mcp.json").read_text())
    assert root_mcp_config == {
        "mcpServers": {
            "endor-cli-tools": {
                "args": ["-y", "endorctl", "ai-tools", "mcp-server"],
                "command": "npx",
                "type": "stdio",
            }
        }
    }
    root_gemini_context = (dest / "GEMINI.md").read_text()
    assert "Do not install the repository root as a" in root_gemini_context
    assert "Install Gemini CLI from `plugins/gemini/endor-labs-agent-kit/`" in root_gemini_context
    assert "Do not load the root Cursor skills as Gemini" in root_gemini_context
    assert "Prefer `endorctl agent api --agent-id <canonical-recipe-id>` lookups" in root_gemini_context
    assert "configure Endor MCP without explicit user approval" in root_gemini_context
    antigravity_plugin_manifest = json.loads(
        (dest / "plugins" / "antigravity" / "endor-labs-agent-kit" / "plugin.json").read_text()
    )
    assert antigravity_plugin_manifest["name"] == "endor-labs-agent-kit"
    assert antigravity_plugin_manifest["description"] == "Endor Labs workflow skills and subagents for Antigravity CLI."
    assert antigravity_plugin_manifest["version"] == gemini_plugin_manifest["version"]
    assert antigravity_plugin_manifest["version"] == "2.1.0"
    assert "mcpServers" not in antigravity_plugin_manifest
    assert "settings" not in antigravity_plugin_manifest
    assert "license" not in antigravity_plugin_manifest
    assert "hooks" not in antigravity_plugin_manifest
    cursor_plugin_manifest = json.loads((dest / ".cursor-plugin" / "plugin.json").read_text())
    assert cursor_plugin_manifest["name"] == "endorlabs"
    assert cursor_plugin_manifest["displayName"] == "Endor Labs Agent Kit"
    assert cursor_plugin_manifest["version"] == gemini_plugin_manifest["version"]
    assert cursor_plugin_manifest["author"]["url"] == "https://www.endorlabs.com/"
    assert cursor_plugin_manifest["logo"] == "assets/logo.png"
    assert cursor_plugin_manifest["agents"] == "./agents/"
    assert cursor_plugin_manifest["skills"] == "./skills/"
    assert cursor_plugin_manifest["hooks"] == "./hooks/hooks.json"
    assert "gemini-extension.json" not in cursor_plugin_manifest
    assert "mcpServers" not in cursor_plugin_manifest
    assert "settings" not in cursor_plugin_manifest

    local_codex_marketplace = json.loads(
        (dest / "plugins" / "codex" / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert local_codex_marketplace["name"] == "endor-labs-agent-kit"
    assert local_codex_marketplace["plugins"][0]["source"]["path"] == "./endor-labs-agent-kit"
    assert local_codex_marketplace["plugins"][0]["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    public_codex_marketplace = json.loads((dest / ".agents" / "plugins" / "marketplace.json").read_text())
    assert public_codex_marketplace["name"] == "endor-labs-agent-kit"
    assert public_codex_marketplace["plugins"][0]["source"]["path"] == "./plugins/codex/endor-labs-agent-kit"
    assert public_codex_marketplace["plugins"][0]["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    claude_marketplace = json.loads((dest / ".claude-plugin" / "marketplace.json").read_text())
    assert claude_marketplace["name"] == "endorlabs"
    assert claude_marketplace["owner"]["name"] == "Endor Labs"
    claude_marketplace_plugins = {
        plugin["name"]: plugin for plugin in claude_marketplace["plugins"]
    }
    assert claude_marketplace_plugins["endor-labs-agent-kit"]["source"] == "./plugins/claude/endor-labs-agent-kit"
    assert claude_marketplace_plugins["endor-labs-agent-kit"]["version"] == claude_plugin_manifest["version"]
    assert claude_discovery_terms <= set(claude_marketplace_plugins["endor-labs-agent-kit"]["tags"])
    assert claude_discovery_terms <= set(claude_marketplace_plugins["endor-labs-agent-kit"]["keywords"])
    assert claude_marketplace_plugins["ai-plugins"]["source"] == "./plugins/claude/ai-plugins"
    assert claude_marketplace_plugins["ai-plugins"]["version"] == legacy_claude_plugin_manifest["version"]
    assert claude_discovery_terms <= set(claude_marketplace_plugins["ai-plugins"]["tags"])
    assert claude_discovery_terms <= set(claude_marketplace_plugins["ai-plugins"]["keywords"])
    local_claude_marketplace = json.loads(
        (dest / "plugins" / "claude" / ".claude-plugin" / "marketplace.json").read_text()
    )
    assert local_claude_marketplace["name"] == "endorlabs"
    assert local_claude_marketplace["owner"]["name"] == "Endor Labs"
    local_claude_marketplace_plugins = {
        plugin["name"]: plugin for plugin in local_claude_marketplace["plugins"]
    }
    assert local_claude_marketplace_plugins["endor-labs-agent-kit"]["source"] == "./endor-labs-agent-kit"
    assert local_claude_marketplace_plugins["endor-labs-agent-kit"]["version"] == claude_plugin_manifest["version"]
    assert claude_discovery_terms <= set(local_claude_marketplace_plugins["endor-labs-agent-kit"]["tags"])
    assert claude_discovery_terms <= set(local_claude_marketplace_plugins["endor-labs-agent-kit"]["keywords"])
    assert local_claude_marketplace_plugins["ai-plugins"]["source"] == "./ai-plugins"
    assert local_claude_marketplace_plugins["ai-plugins"]["version"] == legacy_claude_plugin_manifest["version"]
    assert claude_discovery_terms <= set(local_claude_marketplace_plugins["ai-plugins"]["tags"])
    assert claude_discovery_terms <= set(local_claude_marketplace_plugins["ai-plugins"]["keywords"])
    cursor_marketplace = json.loads((dest / ".cursor-plugin" / "marketplace.json").read_text())
    assert cursor_marketplace["name"] == "endorlabs"
    assert cursor_marketplace["plugins"][0]["name"] == "endorlabs"
    assert cursor_marketplace["plugins"][0]["source"] == "./"
    assert cursor_marketplace["plugins"][0]["version"] == cursor_plugin_manifest["version"]
    cursor_sdk_definitions = json.loads((dest / "cursor-sdk" / "agent_definitions.json").read_text())
    assert cursor_sdk_definitions["sdk"] == "cursor-python"
    assert cursor_sdk_definitions["default_model"] == "composer-2.5"
    cursor_sdk_agents = {
        agent["id"]: agent
        for agent in cursor_sdk_definitions["agents"]
    }
    assert set(cursor_sdk_agents) == set(cursor_sdk_agent_ids) | {"endor-agent-kit-setup"}
    assert cursor_sdk_agents["endor-agent-kit-setup"]["agent_name"] == "endor-agent-kit-setup-agent"
    assert cursor_sdk_agents["endor-agent-kit-setup"]["readonly"] is True
    assert cursor_sdk_agents["ai-sast-remediation"]["readonly"] is False
    assert cursor_sdk_agents["cicd-posture"]["readonly"] is True
    assert cursor_sdk_agents["cicd-posture"]["prompt_file"] == "agents/endor-cicd-posture-agent.md"
    assert cursor_sdk_agents["sca-remediation"]["readonly"] is False
    assert cursor_sdk_agents["configuration-automation"]["readonly"] is True
    assert cursor_sdk_agents["configuration-automation"]["prompt_file"] == "agents/endor-configuration-automation-agent.md"
    assert cursor_sdk_agents["findings-browser"]["readonly"] is True
    assert cursor_sdk_agents["findings-browser"]["prompt_file"] == "agents/endor-findings-browser-agent.md"

    setup = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "Run `endorctl scan`" in setup
    assert "Run `endorctl host-check`" in setup
    assert "must not" in setup
    assert "provenance-gated updates" in setup
    assert "agents and skills" in setup
    assert "--agents-only" in setup
    assert "--skills-only" in setup
    codex_setup_agent = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "agents"
        / "endor-agent-kit-setup-agent.toml"
    ).read_text()
    assert "Codex Host Contract" in codex_setup_agent
    assert "endor-agent-kit-setup" in codex_setup_agent
    claude_setup = (
        dest
        / "plugins"
        / "claude"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "Run `endorctl scan`" in claude_setup
    assert "Run `endorctl host-check`" in claude_setup
    assert "Do not add plugin-wide MCP automatically" in claude_setup
    legacy_claude_setup = (
        dest
        / "plugins"
        / "claude"
        / "ai-plugins"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "retained for existing Claude Code users and pinned installs" in legacy_claude_setup
    assert "Do not enable both Claude plugin ids in the same profile" in legacy_claude_setup
    assert "does not auto-disable, uninstall, or edit Claude settings" in legacy_claude_setup
    assert "/plugin install ai-plugins@endorlabs" in legacy_claude_setup
    primary_claude_setup = (
        dest
        / "plugins"
        / "claude"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "preferred Claude Code plugin id for new installs" in primary_claude_setup
    assert "Existing `ai-plugins@endorlabs` users can keep using" in primary_claude_setup
    assert "does not auto-disable, uninstall, or edit Claude settings" in primary_claude_setup
    gemini_setup = (
        dest
        / "plugins"
        / "gemini"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "Run `endorctl scan`" in gemini_setup
    assert "Run `endorctl host-check`" in gemini_setup
    assert "folder trust prompt" in gemini_setup
    assert "tagged GitHub repository" in gemini_setup
    assert "https://github.com/endorlabs/ai-plugins" in gemini_setup
    assert "gemini extensions install https://github.com/endorlabs/ai-plugins" not in gemini_setup
    assert "gemini extensions install ./ai-plugins/plugins/gemini/endor-labs-agent-kit" in gemini_setup
    assert "zip archives" in gemini_setup
    assert "Do not add plugin-wide MCP automatically" in gemini_setup
    assert "Require `endorctl agent api --help` to succeed" in gemini_setup
    assert "npx -y endorctl ai-tools mcp-server" in gemini_setup
    assert "validate in a fresh host session" in gemini_setup
    assert "Gemini subagents are preview functionality" in gemini_setup
    antigravity_setup = (
        dest
        / "plugins"
        / "antigravity"
        / "endor-labs-agent-kit"
        / "skills"
        / "endor-agent-kit-setup"
        / "SKILL.md"
    ).read_text()
    assert "Run `endorctl scan`" in antigravity_setup
    assert "Run `endorctl host-check`" in antigravity_setup
    assert "antigravity plugin validate" in antigravity_setup
    assert "Do not add plugin-wide MCP automatically" in antigravity_setup
    assert "Require `endorctl agent api --help` to succeed" in antigravity_setup
    assert "Invoke bundled subagents as `@agent-name`" in antigravity_setup
    assert "evidence_queries" in antigravity_setup
    assert "Antigravity subagents are host-managed" in antigravity_setup
    antigravity_agent = (
        dest
        / "plugins"
        / "antigravity"
        / "endor-labs-agent-kit"
        / "agents"
        / "sca-remediation.md"
    ).read_text()
    assert "Invoke workflow subagents as `@agent-name`" in antigravity_agent
    assert "Do not narrate tool-planning chatter" in antigravity_agent
    assert "non-empty `data_gaps`" in antigravity_agent
    cursor_setup = (
        dest / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    ).read_text()
    assert "Endor Agent Kit Setup For Cursor" in cursor_setup
    assert "Run `endorctl scan`" in cursor_setup
    assert "Run `endorctl host-check`" in cursor_setup
    assert "separate from the Gemini CLI extension" in cursor_setup
    assert "Do not add plugin-wide MCP automatically" in cursor_setup
    assert "Require `endorctl agent api --help` to succeed" in cursor_setup
    cursor_skill = (dest / "skills" / "configuration-automation" / "SKILL.md").read_text()
    assert "Cursor Host Contract" in cursor_skill
    assert (
        "These instructions apply only when this skill is used through the Cursor host integration."
        in cursor_skill
    )
    assert "Gemini CLI Host Contract" not in cursor_skill
    cursor_findings_skill = (dest / "skills" / "findings-browser" / "SKILL.md").read_text()
    assert "Cursor Host Contract" in cursor_findings_skill
    assert "findings_verdict" in cursor_findings_skill
    cursor_cicd_skill = (dest / "skills" / "cicd-posture" / "SKILL.md").read_text()
    assert "Cursor Host Contract" in cursor_cicd_skill
    assert "CI/CD Posture Evidence Contract" in cursor_cicd_skill
    cursor_agent = (dest / "agents" / "endor-configuration-automation-agent.md").read_text()
    assert "endor_agent_kit_managed=true" in cursor_agent
    assert "name: endor-configuration-automation-agent" in cursor_agent.split("---", 2)[1]
    assert "model: inherit" in cursor_agent.split("---", 2)[1]
    assert "readonly: true" in cursor_agent.split("---", 2)[1]
    assert "Cursor Host Contract" in cursor_agent
    assert "matching support skill `skills/configuration-automation/`" in cursor_agent
    assert "Gemini CLI Host Contract" not in cursor_agent
    cursor_cicd_agent = (dest / "agents" / "endor-cicd-posture-agent.md").read_text()
    assert "readonly: true" in cursor_cicd_agent.split("---", 2)[1]
    assert "matching support skill `skills/cicd-posture/`" in cursor_cicd_agent
    assert "score_validation" in cursor_cicd_agent
    cursor_sast_agent = (dest / "agents" / "endor-ai-sast-remediation-agent.md").read_text()
    assert "readonly: false" in cursor_sast_agent.split("---", 2)[1]
    cursor_mutating_agent = (dest / "agents" / "endor-sca-remediation-agent.md").read_text()
    assert "readonly: false" in cursor_mutating_agent.split("---", 2)[1]
    cursor_setup_agent = (dest / "agents" / "endor-agent-kit-setup-agent.md").read_text()
    assert "Endor Agent Kit Setup Agent For Cursor" in cursor_setup_agent
    assert "agents/" in cursor_setup_agent
    assert "skills/" in cursor_setup_agent
    assert "separate from the Gemini CLI extension" in cursor_setup_agent
    cursor_sdk_readme = (dest / "cursor-sdk" / "README.md").read_text()
    assert "uv pip install -r requirements.txt" in cursor_sdk_readme
    assert "python3 -m pip install -r requirements.txt" in cursor_sdk_readme
    assert "python run_cursor_agent.py endor-configuration-automation-agent" in cursor_sdk_readme
    assert "endor-cicd-posture-agent" in cursor_sdk_readme
    assert "python run_cursor_agent.py endor-sca-remediation-agent" in cursor_sdk_readme
    assert "python3 -m pip install -r cursor-sdk/requirements.txt" not in cursor_sdk_readme
    assert "python cursor-sdk/run_cursor_agent.py" not in cursor_sdk_readme
    assert "Cursor Python SDK" in cursor_sdk_readme
    assert "Filter > Source > SDK" in cursor_sdk_readme
    assert "must not run `endorctl scan` or `endorctl host-check`" in cursor_sdk_readme
    cursor_sdk_runner = (dest / "cursor-sdk" / "run_cursor_agent.py").read_text()
    assert "from cursor_sdk import Agent, CloudAgentOptions, CloudRepository, LocalAgentOptions" in cursor_sdk_runner
    assert "agent_definitions.json" in cursor_sdk_runner
    assert "CURSOR_API_KEY" in cursor_sdk_runner
    assert "import sys" not in cursor_sdk_runner
    assert "Cloud repository: {args.repo_url}" in cursor_sdk_runner
    assert "Cloud ref: {args.ref}" in cursor_sdk_runner
    assert "Local workspace: {workspace}" in cursor_sdk_runner
    assert "Workspace: {workspace}" not in cursor_sdk_runner
    assert "From cursor-sdk, run: " in cursor_sdk_runner
    assert "python3 -m pip install -r requirements.txt" in cursor_sdk_runner
    assert "python3 -m pip install -r cursor-sdk/requirements.txt" in cursor_sdk_runner
    cursor_sdk_prompt = (dest / "cursor-sdk" / "agents" / "endor-configuration-automation-agent.md").read_text()
    assert "Cursor SDK Host Contract" in cursor_sdk_prompt
    assert "host=cursor-sdk" in cursor_sdk_prompt
    assert "Gemini CLI Host Contract" not in cursor_sdk_prompt
    cursor_sdk_cicd_prompt = (dest / "cursor-sdk" / "agents" / "endor-cicd-posture-agent.md").read_text()
    assert "Cursor SDK Host Contract" in cursor_sdk_cicd_prompt
    assert "host=cursor-sdk" in cursor_sdk_cicd_prompt
    assert "score_validation" in cursor_sdk_cicd_prompt
    cursor_sdk_setup = (dest / "cursor-sdk" / "agents" / "endor-agent-kit-setup-agent.md").read_text()
    assert "Endor Agent Kit Setup Agent For Cursor SDK" in cursor_sdk_setup
    assert "Run `endorctl scan`" in cursor_sdk_setup
    assert "Run `endorctl host-check`" in cursor_sdk_setup

    toml = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "agents"
        / "endor-configuration-automation-agent.toml"
    ).read_text()
    assert "# endor_agent_kit_managed = true" in toml
    assert 'name = "endor-configuration-automation-agent"' in toml
    assert 'sandbox_mode = "read-only"' in toml
    assert "Codex Host Contract" in toml
    assert "developer_instructions = " in toml

    mutating_toml = (
        dest
        / "plugins"
        / "codex"
        / "endor-labs-agent-kit"
        / "agents"
        / "endor-sca-remediation-agent.toml"
    ).read_text()
    assert 'name = "endor-sca-remediation-agent"' in mutating_toml
    assert "sandbox_mode" not in mutating_toml
    for agent_toml in sorted((dest / "plugins" / "codex" / "endor-labs-agent-kit" / "agents").glob("*.toml")):
        parsed_agent = tomllib.loads(agent_toml.read_text())
        assert parsed_agent["name"].startswith("endor-")
        assert parsed_agent["developer_instructions"]
    claude_mcp_agent = (
        dest
        / "plugins"
        / "claude"
        / "endor-labs-agent-kit"
        / "agents"
        / "dependency-reviewer.md"
    ).read_text()
    assert "mcpServers:" not in claude_mcp_agent.split("---", 2)[1]
    assert "Claude Code Plugin Setup Note" in claude_mcp_agent
    assert "does not declare plugin-wide MCP" in claude_mcp_agent
    claude_mcp_only_agent = (
        dest
        / "plugins"
        / "claude"
        / "endor-labs-agent-kit"
        / "agents"
        / "vulnerability-explainer.md"
    ).read_text()
    assert "mcpServers:" not in claude_mcp_only_agent.split("---", 2)[1]
    assert "Bash" not in {
        tool.strip()
        for tool in next(
            line
            for line in claude_mcp_only_agent.split("---", 2)[1].splitlines()
            if line.startswith("disallowedTools:")
        )
        .removeprefix("disallowedTools:")
        .split(",")
    }
    assert "endorctl agent api --agent-id vulnerability-explainer" in claude_mcp_only_agent
    gemini_agent = (
        dest
        / "plugins"
        / "gemini"
        / "endor-labs-agent-kit"
        / "agents"
        / "configuration-automation.md"
    ).read_text()
    assert "endor_agent_kit_managed=true" in gemini_agent
    assert "Gemini CLI Host Contract" in gemini_agent
    assert "data_gaps" in gemini_agent
    assert "kind: local" in gemini_agent.split("---", 2)[1]
    assert "mcpServers:" not in gemini_agent.split("---", 2)[1]
    antigravity_agent = (
        dest
        / "plugins"
        / "antigravity"
        / "endor-labs-agent-kit"
        / "agents"
        / "configuration-automation.md"
    ).read_text()
    assert "endor_agent_kit_managed=true" in antigravity_agent
    assert "Antigravity CLI Host Contract" in antigravity_agent
    assert "data_gaps" in antigravity_agent
    assert "kind: local" in antigravity_agent.split("---", 2)[1]
    assert "mcpServers:" not in antigravity_agent.split("---", 2)[1]

    manifest = json.loads((dest / "manifest.json").read_text())
    packages = {
        (package["host"], package["name"]): package
        for package in manifest["plugin_packages"]
    }
    assert set(packages) == {
        ("antigravity", "endor-labs-agent-kit"),
            ("claude-code", "ai-plugins"),
            ("claude-code", "endor-labs-agent-kit"),
            ("codex", "endor-labs-agent-kit"),
            ("cursor", "endorlabs"),
            ("cursor-sdk", "endor-labs-agent-kit-cursor-sdk"),
            ("gemini", "endor-labs-agent-kit"),
        }
    assert packages[("codex", "endor-labs-agent-kit")] == {
        "artifacts": packages[("codex", "endor-labs-agent-kit")]["artifacts"],
        "display_name": "Endor Labs Agent Kit",
        "host": "codex",
        "included_agents": list(codex_agent_ids),
        "marketplace_path": ".agents/plugins/marketplace.json",
        "name": "endor-labs-agent-kit",
        "path": "plugins/codex/endor-labs-agent-kit",
        "version": plugin_manifest["version"],
    }
    assert packages[("claude-code", "endor-labs-agent-kit")] == {
        "artifacts": packages[("claude-code", "endor-labs-agent-kit")]["artifacts"],
        "display_name": "Endor Labs Agent Kit",
        "host": "claude-code",
        "included_agents": list(claude_agent_ids),
        "marketplace_path": ".claude-plugin/marketplace.json",
        "name": "endor-labs-agent-kit",
        "path": "plugins/claude/endor-labs-agent-kit",
        "version": claude_plugin_manifest["version"],
    }
    assert packages[("claude-code", "ai-plugins")] == {
        "artifacts": packages[("claude-code", "ai-plugins")]["artifacts"],
        "display_name": "Endor Labs AI Plugins (Legacy)",
        "host": "claude-code",
        "included_agents": list(claude_agent_ids),
        "marketplace_path": ".claude-plugin/marketplace.json",
        "name": "ai-plugins",
        "path": "plugins/claude/ai-plugins",
        "version": legacy_claude_plugin_manifest["version"],
    }
    assert packages[("gemini", "endor-labs-agent-kit")] == {
        "artifacts": packages[("gemini", "endor-labs-agent-kit")]["artifacts"],
        "display_name": "Endor Labs Agent Kit",
        "host": "gemini",
        "included_agents": list(gemini_agent_ids),
        "name": "endor-labs-agent-kit",
        "path": "plugins/gemini/endor-labs-agent-kit",
        "version": gemini_plugin_manifest["version"],
    }
    assert packages[("antigravity", "endor-labs-agent-kit")] == {
        "artifacts": packages[("antigravity", "endor-labs-agent-kit")]["artifacts"],
        "display_name": "Endor Labs Agent Kit",
        "host": "antigravity",
        "included_agents": list(antigravity_agent_ids),
        "name": "endor-labs-agent-kit",
        "path": "plugins/antigravity/endor-labs-agent-kit",
        "version": antigravity_plugin_manifest["version"],
    }
    assert packages[("cursor", "endorlabs")] == {
        "artifacts": packages[("cursor", "endorlabs")]["artifacts"],
        "display_name": "Endor Labs Agent Kit",
        "host": "cursor",
        "included_agents": list(cursor_agent_ids),
        "marketplace_path": ".cursor-plugin/marketplace.json",
        "name": "endorlabs",
        "path": ".",
        "version": cursor_plugin_manifest["version"],
    }
    assert packages[("cursor-sdk", "endor-labs-agent-kit-cursor-sdk")] == {
        "artifacts": packages[("cursor-sdk", "endor-labs-agent-kit-cursor-sdk")]["artifacts"],
        "display_name": "Endor Labs Agent Kit Cursor SDK",
        "host": "cursor-sdk",
        "included_agents": list(cursor_sdk_agent_ids),
        "name": "endor-labs-agent-kit-cursor-sdk",
        "path": "cursor-sdk",
        "version": cursor_plugin_manifest["version"],
    }
    package_artifact_paths = {
        artifact["path"]
        for artifact in packages[("codex", "endor-labs-agent-kit")]["artifacts"]
    }
    assert "plugins/codex/endor-labs-agent-kit/README.md" in package_artifact_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/hooks.json" in package_artifact_paths
    assert "plugins/codex/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in package_artifact_paths
    assert ".agents/plugins/marketplace.json" in package_artifact_paths
    assert "plugins/codex/.agents/plugins/marketplace.json" in package_artifact_paths
    assert "plugins/README.md" in package_artifact_paths
    claude_artifact_paths = {
        artifact["path"]
        for artifact in packages[("claude-code", "endor-labs-agent-kit")]["artifacts"]
    }
    assert "plugins/claude/endor-labs-agent-kit/README.md" in claude_artifact_paths
    assert ".claude-plugin/marketplace.json" in claude_artifact_paths
    assert "plugins/claude/.claude-plugin/marketplace.json" in claude_artifact_paths
    assert "plugins/README.md" in claude_artifact_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/hooks.json" in claude_artifact_paths
    assert "plugins/claude/endor-labs-agent-kit/hooks/suggest-endor-tools.sh" in claude_artifact_paths
    legacy_claude_artifact_paths = {
        artifact["path"]
        for artifact in packages[("claude-code", "ai-plugins")]["artifacts"]
    }
    assert "plugins/claude/ai-plugins/README.md" in legacy_claude_artifact_paths
    assert ".claude-plugin/marketplace.json" in legacy_claude_artifact_paths
    assert "plugins/claude/.claude-plugin/marketplace.json" in legacy_claude_artifact_paths
    assert "plugins/README.md" in legacy_claude_artifact_paths
    assert not any("/hooks/" in path for path in legacy_claude_artifact_paths)
    gemini_artifact_paths = {
        artifact["path"]
        for artifact in packages[("gemini", "endor-labs-agent-kit")]["artifacts"]
    }
    assert "plugins/gemini/endor-labs-agent-kit/README.md" in gemini_artifact_paths
    assert "plugins/gemini/endor-labs-agent-kit/hooks/hooks.json" in gemini_artifact_paths
    assert "plugins/gemini/endor-labs-agent-kit.zip" not in gemini_artifact_paths
    assert "plugins/README.md" in gemini_artifact_paths
    antigravity_artifact_paths = {
        artifact["path"]
        for artifact in packages[("antigravity", "endor-labs-agent-kit")]["artifacts"]
    }
    assert "plugins/antigravity/endor-labs-agent-kit/README.md" in antigravity_artifact_paths
    assert "plugins/antigravity/endor-labs-agent-kit/plugin.json" in antigravity_artifact_paths
    assert "plugins/antigravity/endor-labs-agent-kit/hooks.json" in antigravity_artifact_paths
    assert "plugins/README.md" in antigravity_artifact_paths
    cursor_artifact_paths = {
        artifact["path"]
        for artifact in packages[("cursor", "endorlabs")]["artifacts"]
    }
    assert ".cursor-plugin/plugin.json" in cursor_artifact_paths
    assert ".cursor-plugin/marketplace.json" in cursor_artifact_paths
    assert "hooks/hooks.json" in cursor_artifact_paths
    assert "agents/endor-configuration-automation-agent.md" in cursor_artifact_paths
    assert "agents/endor-findings-browser-agent.md" in cursor_artifact_paths
    assert "agents/endor-cicd-posture-agent.md" in cursor_artifact_paths
    assert "agents/endor-sca-remediation-agent.md" in cursor_artifact_paths
    assert "agents/endor-agent-kit-setup-agent.md" in cursor_artifact_paths
    assert "skills/configuration-automation/SKILL.md" in cursor_artifact_paths
    assert "skills/configuration-automation/architecture.svg" in cursor_artifact_paths
    assert "skills/findings-browser/SKILL.md" in cursor_artifact_paths
    assert "skills/findings-browser/architecture.svg" in cursor_artifact_paths
    assert "skills/cicd-posture/SKILL.md" in cursor_artifact_paths
    assert "skills/cicd-posture/architecture.svg" in cursor_artifact_paths
    assert "GEMINI.md" not in cursor_artifact_paths
    assert "gemini-extension.json" not in cursor_artifact_paths
    cursor_sdk_artifact_paths = {
        artifact["path"]
        for artifact in packages[("cursor-sdk", "endor-labs-agent-kit-cursor-sdk")]["artifacts"]
    }
    assert "cursor-sdk/README.md" in cursor_sdk_artifact_paths
    assert "cursor-sdk/run_cursor_agent.py" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agent_definitions.json" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agents/endor-configuration-automation-agent.md" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agents/endor-findings-browser-agent.md" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agents/endor-cicd-posture-agent.md" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agents/endor-sca-remediation-agent.md" in cursor_sdk_artifact_paths
    assert "cursor-sdk/agents/endor-agent-kit-setup-agent.md" in cursor_sdk_artifact_paths
    assert not (dest / "plugins" / "gemini" / "endor-labs-agent-kit.zip").exists()


def test_generated_codex_agent_installer_runs_against_temp_codex_home(tmp_path):
    recipes = [
        _copy_agent(tmp_path / "troubleshooter", "troubleshooting"),
        _copy_agent(tmp_path / "sca", "sca-remediation"),
    ]
    dest = tmp_path / "endor-labs-agent-kit"
    publish_recipes(recipes, dest, include_plugins=True)
    script = dest / "plugins" / "codex" / "endor-labs-agent-kit" / "scripts" / "install_codex_agents.py"
    codex_home = tmp_path / "codex-home"
    skills_home = tmp_path / "agents-home" / "skills"

    status = subprocess.run(
        [
            sys.executable,
            str(script),
            "--status",
            "--codex-home",
            str(codex_home),
            "--skills-home",
            str(skills_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "endor-sca-remediation-agent.toml: missing" in status.stdout
    assert "endor-troubleshooting-agent.toml: missing" in status.stdout
    assert "skill:sca-remediation: missing" in status.stdout
    assert "skill:endor-agent-kit-setup: missing" in status.stdout

    install = subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--yes",
            "--codex-home",
            str(codex_home),
            "--skills-home",
            str(skills_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "installed" in install.stdout
    assert (codex_home / "agents" / "endor-sca-remediation-agent.toml").is_file()
    assert (codex_home / "agents" / "endor-troubleshooting-agent.toml").is_file()
    assert (codex_home / "agents" / "endor-agent-kit-setup-agent.toml").is_file()
    assert (skills_home / "sca-remediation" / "SKILL.md").is_file()
    assert (skills_home / "endor-agent-kit-setup" / "SKILL.md").is_file()

    current = subprocess.run(
        [
            sys.executable,
            str(script),
            "--status",
            "--codex-home",
            str(codex_home),
            "--skills-home",
            str(skills_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "endor-sca-remediation-agent.toml: current" in current.stdout
    assert "endor-troubleshooting-agent.toml: current" in current.stdout
    assert "skill:sca-remediation: current" in current.stdout
    assert "skill:endor-agent-kit-setup: current" in current.stdout

    unmanaged_skill = skills_home / "sca-remediation" / "SKILL.md"
    unmanaged_skill.write_text("# unmanaged user skill\n", encoding="utf-8")
    blocked = subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--yes",
            "--skills-only",
            "--codex-home",
            str(codex_home),
            "--skills-home",
            str(skills_home),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert blocked.returncode == 1
    assert "refusing to overwrite blocked unmanaged skill" in blocked.stdout
    assert unmanaged_skill.read_text(encoding="utf-8") == "# unmanaged user skill\n"


def test_cli_publish_accepts_multiple_recipes(tmp_path, capsys):
    dependency_recipe = _copy_agent(tmp_path / "dependency", "dependency-reviewer")
    upgrade_recipe = _copy_agent(tmp_path / "upgrade", "oss-upgrade-investigator")
    vulnerability_recipe = _copy_agent(tmp_path / "vulnerability", "vulnerability-explainer")
    dest = tmp_path / "endor-labs-agent-kit"

    status = main([
        "publish",
        str(dependency_recipe),
        str(upgrade_recipe),
        str(vulnerability_recipe),
        "--dest",
        str(dest),
    ])
    output = capsys.readouterr().out

    assert status == 0
    assert "dependency-reviewer.md" in output
    assert "oss-upgrade-investigator.md" in output
    assert "vulnerability-explainer.md" in output
    assert "claude-managed-agents/oss-upgrade-investigator/agent.yaml" in output
    assert "claude-managed-agents/dependency-reviewer/agent.yaml" in output
    manifest = json.loads((dest / "manifest.json").read_text())
    assert [(agent["host"], agent["id"]) for agent in manifest["agents"]] == [
        ("claude-code", "dependency-reviewer"),
        ("claude-code", "oss-upgrade-investigator"),
        ("claude-code", "vulnerability-explainer"),
        ("claude-managed-agents", "dependency-reviewer"),
        ("claude-managed-agents", "oss-upgrade-investigator"),
        ("claude-managed-agents", "vulnerability-explainer"),
        ("codex", "dependency-reviewer"),
        ("codex", "oss-upgrade-investigator"),
        ("codex", "vulnerability-explainer"),
        ("gemini", "dependency-reviewer"),
        ("gemini", "oss-upgrade-investigator"),
        ("gemini", "vulnerability-explainer"),
        ("portable", "dependency-reviewer"),
        ("portable", "oss-upgrade-investigator"),
        ("portable", "vulnerability-explainer"),
    ]
    root_readme = (dest / "README.md").read_text()
    assert "## Start Here" in root_readme
    assert "docs/getting-started.md" in root_readme
    assert "docs/for-agents.md" in root_readme
    assert "docs/maintainer-guide.md" in root_readme
    assert "docs/distribution-sync.md" in root_readme
    assert "## Agent Quick Start" in root_readme
    assert "llms.txt" in root_readme
    assert "## Table Of Contents" in root_readme
    assert "## Contribute An Agent" in root_readme
    assert "## Recipe Reference" in root_readme
    assert "### Ask An LLM To Install It" in root_readme
    assert "Preserve the generated agent prompt exactly" in root_readme
    assert "host_capabilities_required.read_files: true" in root_readme
    assert "Claude Code artifacts allow only `Read`, `Glob`, `Grep`, and `LS`" in root_readme
    assert "Review an exact package decision, package risk, or repository dependencies through one bounded profile" in root_readme
    assert "@agent-dependency-reviewer review this repository's dependency manifests" in root_readme
    assert "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune" in root_readme
    assert "endor-agent-kit validate-sca-output sca-output.json --gate selection-plan" in root_readme
    assert "endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md" in root_readme
    assert "endor-agent-kit lint-sca-pr-body pr-body.md" in root_readme
    assert "endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo" in root_readme
    assert "endor-agent-kit check-install --host claude-managed-agents --agent configuration-automation" in root_readme
    assert "endor-agent-kit check-install --host codex --agent sca-remediation --skills-home ~/.agents/skills" in root_readme
    assert "$HOME/.agents/skills/<agent>" in root_readme
    assert "$CODEX_HOME/skills" not in root_readme
    assert "OSS Upgrade Investigator" in root_readme
    assert "Dependency Reviewer" in root_readme
    assert "claude-code/oss-upgrade-investigator/" in root_readme
    assert "claude-managed-agents/oss-upgrade-investigator/" in root_readme
    assert "claude-code/dependency-reviewer/" in root_readme
    assert "claude-managed-agents/dependency-reviewer/" in root_readme
    assert "claude-code/dependency-reviewer/" in root_readme
    assert "portable/dependency-reviewer/" in root_readme


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
