from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import repo_root
from endor_agent_kit.catalog_manifest import CatalogManifest
from endor_agent_kit.cli import main
from endor_agent_kit.install import (
    check_claude_code_install,
    check_claude_managed_agents_install,
    check_codex_install,
    check_portable_install,
)
from endor_agent_kit.publisher import publish_recipes


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _copy_agent_source(tmp_path: Path, agent_id: str) -> Path:
    source = repo_root() / "source" / "agents" / agent_id
    target = tmp_path / agent_id
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("dist"))
    return target / "recipe.yaml"


def _write_catalog_manifest(
    catalog_root: Path,
    *,
    agent_id: str = "sca-remediation",
    host: str = "claude-code",
    bundle_path: str | None = None,
    primary_artifact_name: str = "sca-remediation.md",
    primary_content: str = "current",
    primary_artifact_path: str | None = None,
    extra_artifacts: list[dict] | None = None,
) -> None:
    catalog_root.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_path or f"{host}/{agent_id}"
    primary_artifact_path = primary_artifact_path or f"{bundle_path}/{primary_artifact_name}"
    artifacts = [
        {
            "path": primary_artifact_path,
            "sha256": _sha256_text(primary_content),
            "bytes": len(primary_content.encode("utf-8")),
        }
    ]
    artifacts.extend(extra_artifacts or [])
    (catalog_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_by": "endor-agent-kit",
                "agents": [
                    {
                        "id": agent_id,
                        "name": "SCA Remediation",
                        "version": "1.0.0",
                        "host": host,
                        "source": {
                            "recipe_schema_version": 2,
                            "builder_recipe": f"source/agents/{agent_id}/recipe.yaml",
                        },
                        "editions": [
                            {
                                "id": "enterprise-edition",
                                "name": "Enterprise Edition",
                                "path": bundle_path,
                                "artifacts": artifacts,
                                "requires_endorctl": ">=1.0",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_check_install_detects_stale_repo_level_agent_from_manifest(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        primary_artifact_path="catalog-layout/not-hardcoded/sca-remediation.md",
    )
    assert not (catalog / "claude-code" / "sca-remediation" / "sca-remediation.md").exists()

    installed_agent = tmp_path / "repo" / ".claude" / "agents"
    installed_agent.mkdir(parents=True)
    (installed_agent / "sca-remediation.md").write_text("old", encoding="utf-8")

    errors = check_claude_code_install(
        "sca-remediation",
        tmp_path / "repo",
        catalog_root=catalog,
    )

    assert any("is stale" in error for error in errors)

    (installed_agent / "sca-remediation.md").write_text("current", encoding="utf-8")
    assert check_claude_code_install(
        "sca-remediation",
        tmp_path / "repo",
        catalog_root=catalog,
    ) == []


def test_check_claude_code_install_requires_catalogued_profile_variants(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        extra_artifacts=[
            {
                "path": "claude-code/sca-remediation/sca-remediation-evidence-check.md",
                "sha256": _sha256_text("profile-current"),
                "bytes": len("profile-current"),
                "profile_id": "evidence-check",
            },
            {
                "path": "claude-code/sca-remediation/README.md",
                "sha256": _sha256_text("readme"),
                "bytes": len("readme"),
            },
        ],
    )
    installed_agent = tmp_path / "repo" / ".claude" / "agents"
    installed_agent.mkdir(parents=True)
    (installed_agent / "sca-remediation.md").write_text("current", encoding="utf-8")

    missing = check_claude_code_install(
        "sca-remediation",
        tmp_path / "repo",
        catalog_root=catalog,
    )
    assert any("sca-remediation-evidence-check.md" in error for error in missing)
    assert not any("README.md" in error for error in missing)

    profile = installed_agent / "sca-remediation-evidence-check.md"
    profile.write_text("profile-old", encoding="utf-8")
    stale = check_claude_code_install(
        "sca-remediation",
        tmp_path / "repo",
        catalog_root=catalog,
    )
    assert any("sca-remediation-evidence-check.md" in error and "is stale" in error for error in stale)

    profile.write_text("profile-current", encoding="utf-8")
    assert check_claude_code_install(
        "sca-remediation",
        tmp_path / "repo",
        catalog_root=catalog,
    ) == []


def test_catalog_manifest_lookup_returns_full_bundle_record(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        extra_artifacts=[
            {
                "path": "claude-code/sca-remediation/README.md",
                "sha256": _sha256_text("readme"),
                "bytes": len("readme"),
            }
        ],
    )

    manifest = CatalogManifest.load(catalog)
    bundles = manifest.find_bundles("sca-remediation", "claude-code")

    assert len(bundles) == 1
    assert bundles[0].bundle_id == "enterprise-edition"
    assert [artifact.name for artifact in bundles[0].artifacts] == [
        "sca-remediation.md",
        "README.md",
    ]
    assert manifest.primary_artifact(
        "sca-remediation",
        "claude-code",
        "sca-remediation.md",
    ).sha256 == _sha256_text("current")


def test_check_codex_install_compares_manifest_bundle_artifacts(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        host="codex",
        bundle_path="future-plugin-package/skills/sca-remediation",
        primary_artifact_name="SKILL.md",
        primary_artifact_path="future-plugin-package/skills/sca-remediation/SKILL.md",
        extra_artifacts=[
            {
                "path": "future-plugin-package/skills/sca-remediation/README.md",
                "sha256": _sha256_text("readme"),
                "bytes": len("readme"),
            },
            {
                "path": "future-plugin-package/skills/sca-remediation/actions.yaml",
                "sha256": _sha256_text("actions"),
                "bytes": len("actions"),
            },
        ],
    )
    assert not (catalog / "codex" / "sca-remediation" / "SKILL.md").exists()

    skills_home = tmp_path / "agents-home" / "skills"
    installed_skill = skills_home / "sca-remediation"
    installed_skill.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text("current", encoding="utf-8")

    missing_errors = check_codex_install(
        "sca-remediation",
        skills_home,
        catalog_root=catalog,
    )
    assert any("README.md" in error for error in missing_errors)
    assert any("actions.yaml" in error for error in missing_errors)

    (installed_skill / "README.md").write_text("readme", encoding="utf-8")
    (installed_skill / "actions.yaml").write_text("old", encoding="utf-8")

    stale_errors = check_codex_install(
        "sca-remediation",
        skills_home,
        catalog_root=catalog,
    )
    assert any("actions.yaml" in error and "is stale" in error for error in stale_errors)

    (installed_skill / "actions.yaml").write_text("actions", encoding="utf-8")

    assert check_codex_install(
        "sca-remediation",
        skills_home,
        catalog_root=catalog,
    ) == []


def test_generated_codex_installer_manages_agents_and_skills(tmp_path):
    recipes = [
        _copy_agent_source(tmp_path / "troubleshooter", "endor-troubleshooter"),
        _copy_agent_source(tmp_path / "sca", "sca-remediation"),
    ]
    dest = tmp_path / "endor-labs-agent-kit"
    publish_recipes(recipes, dest, include_plugins=True)
    script = dest / "plugins" / "codex" / "endor-labs-agent-kit" / "scripts" / "install_codex_agents.py"
    plugin_manifest = json.loads(
        (dest / "plugins" / "codex" / "endor-labs-agent-kit" / ".codex-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    package_version = plugin_manifest["version"]
    generated_skill = (
        dest / "plugins" / "codex" / "endor-labs-agent-kit" / "skills" / "sca-remediation" / "SKILL.md"
    ).read_text(encoding="utf-8")
    generated_agent = (
        dest / "plugins" / "codex" / "endor-labs-agent-kit" / "agents" / "endor-sca-remediation-agent.toml"
    ).read_text(encoding="utf-8")
    assert f"package `endor-labs-agent-kit` v{package_version}." in generated_skill
    assert '# endor_agent_kit_package_name = "endor-labs-agent-kit"' in generated_agent
    assert f'# endor_agent_kit_package_version = "{package_version}"' in generated_agent
    codex_home = tmp_path / "codex-home"
    skills_home = tmp_path / "agents-home" / "skills"
    stale_cache_manifest = (
        codex_home
        / "plugins"
        / "cache"
        / "endor-agent-kit-local"
        / "endor-agent-kit-security-agents"
        / "0.1.0"
        / ".codex-plugin"
        / "plugin.json"
    )
    stale_cache_manifest.parent.mkdir(parents=True)
    stale_cache_manifest.write_text(
        json.dumps(
            {
                "name": "endor-agent-kit-security-agents",
                "version": "0.1.0",
                "description": "Generated Endor Labs Agent Kit Codex skills.",
                "interface": {"displayName": "Endor Agent Kit Security Agents"},
            }
        ),
        encoding="utf-8",
    )
    config = codex_home / "config.toml"
    config.write_text(
        "\n".join(
            [
                '[plugins."presentations@openai-primary-runtime"]',
                "enabled = true",
                "",
                '[plugins."endor-agent-kit-security-agents@endor-agent-kit-local"]',
                "enabled = true",
                "",
                '[plugins."notion@openai-curated"]',
                "enabled = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

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
    assert "agent:endor-sca-remediation-agent.toml: missing" in status.stdout
    assert "agent:endor-agent-kit-setup-agent.toml: missing" in status.stdout
    assert "skill:sca-remediation: missing" in status.stdout
    assert "skill:endor-agent-kit-setup: missing" in status.stdout
    assert (
        "plugin-cache:plugins/cache/endor-agent-kit-local/endor-agent-kit-security-agents/0.1.0: "
        "stale-legacy-cache package=endor-agent-kit-security-agents version=0.1.0"
    ) in status.stdout
    assert (
        "plugin-config:config.toml:endor-agent-kit-security-agents@endor-agent-kit-local: "
        "stale-legacy-config enabled=true"
    ) in status.stdout
    assert "--purge-stale-plugin-cache --yes" in status.stdout

    stale_cache_root = stale_cache_manifest.parents[1]
    dry_purge = subprocess.run(
        [
            sys.executable,
            str(script),
            "--purge-stale-plugin-cache",
            "--codex-home",
            str(codex_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "would move stale plugin cache" in dry_purge.stdout
    assert "would remove stale legacy entries endor-agent-kit-security-agents@endor-agent-kit-local" in dry_purge.stdout
    assert stale_cache_root.exists()
    assert "endor-agent-kit-security-agents@endor-agent-kit-local" in config.read_text(encoding="utf-8")

    purge = subprocess.run(
        [
            sys.executable,
            str(script),
            "--purge-stale-plugin-cache",
            "--yes",
            "--codex-home",
            str(codex_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "moved stale plugin cache" in purge.stdout
    assert "removed stale legacy entries endor-agent-kit-security-agents@endor-agent-kit-local" in purge.stdout
    assert not stale_cache_root.exists()
    assert list((codex_home / "plugins" / "cache-backups").glob("endor-agent-kit-local-endor-agent-kit-security-agents-0.1.0.bak-*"))
    assert "endor-agent-kit-security-agents@endor-agent-kit-local" not in config.read_text(encoding="utf-8")
    assert list(codex_home.glob("config.toml.bak-*"))

    clean_cache_status = subprocess.run(
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
    assert "plugin-cache: none" in clean_cache_status.stdout
    assert "plugin-config: none" in clean_cache_status.stdout

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--agents-only",
            "--yes",
            "--codex-home",
            str(codex_home),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (codex_home / "agents" / "endor-sca-remediation-agent.toml").is_file()
    assert (codex_home / "agents" / "endor-agent-kit-setup-agent.toml").is_file()
    assert not (skills_home / "sca-remediation" / "SKILL.md").exists()

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--skills-only",
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
    skill = skills_home / "sca-remediation" / "SKILL.md"
    setup_skill = skills_home / "endor-agent-kit-setup" / "SKILL.md"
    assert skill.is_file()
    assert setup_skill.is_file()

    skill.write_text(skill.read_text(encoding="utf-8") + "\nmanaged local edit\n", encoding="utf-8")
    refresh = subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--skills-only",
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
    assert "backed up existing managed skill" in refresh.stdout
    skill_backups = skills_home.parent / "skill-backups" / "endor-agent-kit"
    assert list(skill_backups.glob("sca-remediation.bak-*"))
    assert not list(skills_home.glob("sca-remediation.bak-*"))

    setup_skill.write_text("# unmanaged user setup skill\n", encoding="utf-8")
    blocked = subprocess.run(
        [
            sys.executable,
            str(script),
            "--install",
            "--skills-only",
            "--yes",
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
    assert setup_skill.read_text(encoding="utf-8") == "# unmanaged user setup skill\n"


def test_check_claude_managed_agents_install_compares_manifest_bundle_artifacts(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        agent_id="probe-droid",
        host="claude-managed-agents",
        bundle_path="managed-export/probe-droid",
        primary_artifact_name="agent.yaml",
        primary_artifact_path="managed-export/probe-droid/agent.yaml",
        primary_content="agent",
        extra_artifacts=[
            {
                "path": "managed-export/probe-droid/environment.yaml",
                "sha256": _sha256_text("environment"),
                "bytes": len("environment"),
            },
            {
                "path": "managed-export/probe-droid/session-template.yaml",
                "sha256": _sha256_text("session"),
                "bytes": len("session"),
            },
            {
                "path": "managed-export/probe-droid/README.md",
                "sha256": _sha256_text("readme"),
                "bytes": len("readme"),
            },
        ],
    )

    managed_agent_dir = tmp_path / "copied-managed-agent"
    managed_agent_dir.mkdir()
    (managed_agent_dir / "agent.yaml").write_text("agent", encoding="utf-8")

    missing_errors = check_claude_managed_agents_install(
        "probe-droid",
        managed_agent_dir,
        catalog_root=catalog,
    )
    assert any("environment.yaml" in error for error in missing_errors)
    assert any("session-template.yaml" in error for error in missing_errors)
    assert any("README.md" in error for error in missing_errors)

    (managed_agent_dir / "environment.yaml").write_text("old", encoding="utf-8")
    (managed_agent_dir / "session-template.yaml").write_text("session", encoding="utf-8")
    (managed_agent_dir / "README.md").write_text("readme", encoding="utf-8")

    stale_errors = check_claude_managed_agents_install(
        "probe-droid",
        managed_agent_dir,
        catalog_root=catalog,
    )
    assert any("environment.yaml" in error and "is stale" in error for error in stale_errors)

    (managed_agent_dir / "environment.yaml").write_text("environment", encoding="utf-8")
    assert check_claude_managed_agents_install(
        "probe-droid",
        managed_agent_dir,
        catalog_root=catalog,
    ) == []


def test_check_portable_install_compares_manifest_bundle_artifacts(tmp_path):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        host="portable",
        bundle_path="portable/sca-remediation",
        primary_artifact_name="agent.md",
        primary_artifact_path="portable/sca-remediation/agent.md",
        primary_content="agent",
        extra_artifacts=[
            {
                "path": "portable/sca-remediation/agent.manifest.json",
                "sha256": _sha256_text("manifest"),
                "bytes": len("manifest"),
            },
            {
                "path": "portable/sca-remediation/output-contract.md",
                "sha256": _sha256_text("contract"),
                "bytes": len("contract"),
            },
        ],
    )

    portable_dir = tmp_path / "runtime" / "agents" / "sca-remediation"
    portable_dir.mkdir(parents=True)
    (portable_dir / "agent.md").write_text("agent", encoding="utf-8")
    (portable_dir / "agent.manifest.json").write_text("manifest", encoding="utf-8")

    missing_errors = check_portable_install(
        "sca-remediation",
        portable_dir,
        catalog_root=catalog,
    )
    assert any("output-contract.md" in error for error in missing_errors)

    (portable_dir / "output-contract.md").write_text("old", encoding="utf-8")
    stale_errors = check_portable_install(
        "sca-remediation",
        portable_dir,
        catalog_root=catalog,
    )
    assert any("output-contract.md" in error and "is stale" in error for error in stale_errors)

    (portable_dir / "output-contract.md").write_text("contract", encoding="utf-8")
    assert check_portable_install(
        "sca-remediation",
        portable_dir,
        catalog_root=catalog,
    ) == []


def test_cli_check_install_uses_manifest_checksum(tmp_path, capsys):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(catalog)
    installed_agent = tmp_path / "repo" / ".claude" / "agents"
    installed_agent.mkdir(parents=True)
    (installed_agent / "sca-remediation.md").write_text("current", encoding="utf-8")

    assert main([
        "check-install",
        "--agent",
        "sca-remediation",
        "--repo",
        str(tmp_path / "repo"),
        "--catalog-root",
        str(catalog),
    ]) == 0
    assert "OK:" in capsys.readouterr().out


def test_cli_check_install_supports_managed_agents_default_catalog_bundle(tmp_path, capsys):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        agent_id="probe-droid",
        host="claude-managed-agents",
        bundle_path="claude-managed-agents/probe-droid",
        primary_artifact_name="agent.yaml",
        primary_artifact_path="claude-managed-agents/probe-droid/agent.yaml",
        primary_content="agent",
        extra_artifacts=[
            {
                "path": "claude-managed-agents/probe-droid/environment.yaml",
                "sha256": _sha256_text("environment"),
                "bytes": len("environment"),
            }
        ],
    )
    managed_agent_dir = catalog / "claude-managed-agents" / "probe-droid"
    managed_agent_dir.mkdir(parents=True)
    (managed_agent_dir / "agent.yaml").write_text("agent", encoding="utf-8")
    (managed_agent_dir / "environment.yaml").write_text("environment", encoding="utf-8")

    assert main([
        "check-install",
        "--host",
        "claude-managed-agents",
        "--agent",
        "probe-droid",
        "--catalog-root",
        str(catalog),
    ]) == 0
    output = capsys.readouterr().out
    assert "OK:" in output
    assert str(managed_agent_dir) in output


def test_cli_check_install_uses_codex_skills_home(tmp_path, capsys):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        host="codex",
        bundle_path="codex/sca-remediation",
        primary_artifact_name="SKILL.md",
        primary_artifact_path="codex/sca-remediation/SKILL.md",
    )
    skills_home = tmp_path / "agents-home" / "skills"
    installed_skill = skills_home / "sca-remediation"
    installed_skill.mkdir(parents=True)
    (installed_skill / "SKILL.md").write_text("current", encoding="utf-8")

    assert main([
        "check-install",
        "--host",
        "codex",
        "--agent",
        "sca-remediation",
        "--skills-home",
        str(skills_home),
        "--catalog-root",
        str(catalog),
    ]) == 0
    output = capsys.readouterr().out
    assert "OK:" in output
    assert str(installed_skill / "SKILL.md") in output


def test_cli_check_install_rejects_legacy_codex_home_for_skills(tmp_path, capsys):
    assert main([
        "check-install",
        "--host",
        "codex",
        "--agent",
        "sca-remediation",
        "--codex-home",
        str(tmp_path / "codex-home"),
    ]) == 1
    assert "--codex-home does not control Codex skill installs" in capsys.readouterr().out


def test_cli_check_install_requires_portable_dir(tmp_path, capsys):
    catalog = tmp_path / "catalog"
    _write_catalog_manifest(
        catalog,
        host="portable",
        bundle_path="portable/sca-remediation",
        primary_artifact_name="agent.md",
        primary_artifact_path="portable/sca-remediation/agent.md",
    )

    assert main([
        "check-install",
        "--host",
        "portable",
        "--agent",
        "sca-remediation",
        "--catalog-root",
        str(catalog),
    ]) == 1
    assert "--portable-dir is required" in capsys.readouterr().out
