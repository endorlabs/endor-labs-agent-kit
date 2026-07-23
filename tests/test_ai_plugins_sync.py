from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_ai_plugins_distribution import (
    generated_root_skills,
    sync_distribution,
)
from scripts.validate_marketplace_host_boundaries import (
    validate_marketplace_host_boundaries,
)


def _write(path: Path, content: str = "content\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_source_tree(root: Path) -> None:
    for directory in ("plugins", "cursor-sdk"):
        _write(root / directory / "artifact.txt")
    _write(root / "pyproject.toml", '[project]\nversion = "9.9.9"\n')
    _write(root / ".mcp.json", "{}\n")
    _write(
        root / ".cursor-plugin" / "plugin.json",
        '{"name":"endorlabs","agents":"./agents/","skills":"./skills/",'
        '"hooks":"./hooks/hooks.json"}\n',
    )
    _write(
        root / ".cursor-plugin" / "marketplace.json",
        '{"name":"endorlabs","owner":{"name":"Endor Labs"},'
        '"plugins":[{"name":"endorlabs","source":"./"}]}\n',
    )
    _write(root / "CHANGELOG.md", "# Changelog\n")
    _write(root / "GEMINI.md", "# Gemini\n")
    _write(root / ".claude-plugin" / "marketplace.json", "{}\n")
    _write(
        root / ".claude-plugin" / "plugin.json",
        '{"name":"endor-labs-agent-kit","displayName":"Repository Root Guard"}\n',
    )
    _write(root / ".agents" / "plugins" / "marketplace.json", "{}\n")
    _write(root / "scripts" / "check_repository_hygiene.py", "# hygiene\n")
    _write(root / "scripts" / "build_codex_directory_submission.py", "# builder\n")
    _write(root / "scripts" / "validate_mirror_provenance.py", "# provenance\n")
    _write(
        root / "scripts" / "validate_marketplace_host_boundaries.py",
        "# host boundaries\n",
    )
    _write(
        root
        / "source"
        / "distribution"
        / "ai-plugins-workflows"
        / "build-codex-directory-submission.yml",
        "name: build\n",
    )
    _write(root / "assets" / "logo.png", "<svg />\n")
    _write(
        root / "agents" / "endor-findings-browser-agent.md",
        "---\nname: endor-findings-browser-agent\ndescription: Browse findings.\n"
        "model: composer-2.5[fast=false]\n---\nBrowse findings.\n",
    )
    _write(root / "skills" / "configuration-automation" / "SKILL.md")
    _write(root / "skills" / "create-endor-labs-agent" / "SKILL.md")
    _write(root / "skills" / "endor-agent-kit-setup" / "SKILL.md", "cursor setup\n")
    _write(root / "hooks" / "hooks.json", '{"afterFileEdit": []}\n')
    _write(root / "hooks" / "cursor-hook.sh", "#!/usr/bin/env bash\nexit 0\n")
    claude_root = root / "plugins" / "claude" / "endor-labs-agent-kit"
    _write(
        claude_root / ".claude-plugin" / "plugin.json",
        """{
  "author": {"name": "Endor Labs"},
  "description": "Endor Labs workflow agents and setup for Claude Code.",
  "displayName": "Endor Labs Agent Kit",
  "homepage": "https://github.com/endorlabs/ai-plugins",
  "keywords": ["endor-labs", "security"],
  "name": "endor-labs-agent-kit",
  "repository": "https://github.com/endorlabs/ai-plugins",
  "version": "9.9.9"
}
""",
    )
    _write(
        claude_root / "agents" / "findings-browser.md",
        "---\nname: findings-browser\nmodel: sonnet\n---\nBrowse findings.\n",
    )
    _write(
        claude_root / "skills" / "endor-agent-kit-setup" / "SKILL.md",
        "---\nname: endor-agent-kit-setup\n---\nSet up Endor.\n",
    )
    _write(
        claude_root / "hooks" / "hooks.json",
        """{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "command": "bash \\\"${CLAUDE_PLUGIN_ROOT}/hooks/suggest-endor-tools.sh\\\"",
            "type": "command"
          }
        ],
        "matcher": ""
      }
    ]
  }
}
""",
    )
    _write(
        claude_root / "hooks" / "suggest-endor-tools.sh",
        "#!/usr/bin/env bash\nexit 0\n",
    )


def test_sync_distribution_copies_generated_surfaces_and_prunes_root_skills(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "plugins" / "stale.txt", "stale\n")
    _write(target / "hooks" / "stale-hook.sh", "stale\n")
    _write(target / "assets" / "logo.svg", "<svg />\n")
    _write(target / "skills" / "old-generated-skill" / "SKILL.md", "stale\n")
    _write(target / "gemini-extension.json", "{}\n")
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")

    operations = sync_distribution(source, target)

    assert "configuration-automation" in generated_root_skills(source)
    assert (target / "plugins" / "artifact.txt").read_text(encoding="utf-8") == "content\n"
    assert not (target / "plugins" / "stale.txt").exists()
    assert not (target / "hooks" / "cursor-hook.sh").exists()
    assert not (target / "hooks" / "stale-hook.sh").exists()
    assert (target / "hooks" / "suggest-endor-tools.sh").exists()
    assert not (target / "skills" / "configuration-automation").exists()
    assert (target / "skills" / "endor-agent-kit-setup" / "SKILL.md").exists()
    assert not (target / "skills" / "create-endor-labs-agent").exists()
    assert not (target / "skills" / "old-generated-skill").exists()
    assert (target / "CHANGELOG.md").read_text(encoding="utf-8") == "# Changelog\n"
    assert (target / "GEMINI.md").read_text(encoding="utf-8") == "# Gemini\n"
    assert (target / ".claude-plugin" / "marketplace.json").exists()
    assert (target / ".agents" / "plugins" / "marketplace.json").exists()
    assert (target / "scripts" / "check_repository_hygiene.py").exists()
    assert (target / "scripts" / "build_codex_directory_submission.py").exists()
    assert (target / "scripts" / "validate_mirror_provenance.py").exists()
    assert (target / "scripts" / "validate_marketplace_host_boundaries.py").exists()
    assert (
        target / ".github" / "workflows" / "build-codex-directory-submission.yml"
    ).exists()
    assert (target / "assets" / "logo.png").exists()
    assert not (target / "assets" / "logo.svg").exists()
    assert not (target / "gemini-extension.json").exists()
    assert not (target / ".mcp.json").exists()
    assert "package version: `9.9.9`" in (target / "README.md").read_text(encoding="utf-8")
    root_manifest = (target / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    assert '"name": "ai-plugins"' in root_manifest
    assert '"displayName": "Endor Labs Agent Kit"' in root_manifest
    assert '"version"' not in root_manifest
    assert '"agents"' not in root_manifest
    assert '"skills"' not in root_manifest
    assert '"hooks"' not in root_manifest
    assert (target / "agents" / "findings-browser.md").exists()
    assert not (target / "agents" / "endor-findings-browser-agent.md").exists()
    assert not (target / ".claude-plugin" / "claude-official-root-hooks.json").exists()
    assert not (target / ".cursor-plugin" / "plugin.json").exists()
    cursor_marketplace = json.loads(
        (target / ".cursor-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert cursor_marketplace["plugins"][0]["source"] == (
        "./plugins/cursor/endor-labs-agent-kit"
    )
    cursor_package = target / "plugins" / "cursor" / "endor-labs-agent-kit"
    cursor_manifest = json.loads(
        (cursor_package / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert all(
        field not in cursor_manifest
        for field in ("agents", "skills", "hooks", "mcpServers")
    )
    assert (
        cursor_package
        / "skills"
        / "configuration-automation"
        / "SKILL.md"
    ).exists()
    assert (cursor_package / "agents" / "endor-findings-browser-agent.md").exists()
    assert (cursor_package / "hooks" / "cursor-hook.sh").exists()
    assert (cursor_package / "mcp.json").exists()
    assert not (cursor_package / ".mcp.json").exists()
    assert not (target / "cursor" / "endor-labs-agent-kit").exists()
    assert validate_marketplace_host_boundaries(target) == []
    assert any("sync" in operation for operation in operations)
    assert any("package version -> 9.9.9" in operation for operation in operations)
    assert any("gemini-extension.json" in operation for operation in operations)


def test_sync_distribution_is_idempotent_and_replaces_stale_claude_overlay(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")
    _write(target / ".claude-plugin" / "plugin.json", '{"name":"stale"}\n')

    sync_distribution(source, target)
    first_manifest = (target / ".claude-plugin" / "plugin.json").read_bytes()
    first_hooks = (target / "hooks" / "hooks.json").read_bytes()
    first_cursor_manifest = (
        target
        / "plugins"
        / "cursor"
        / "endor-labs-agent-kit"
        / ".cursor-plugin"
        / "plugin.json"
    ).read_bytes()

    sync_distribution(source, target)

    assert (target / ".claude-plugin" / "plugin.json").read_bytes() == first_manifest
    assert (
        target / "hooks" / "hooks.json"
    ).read_bytes() == first_hooks
    assert (
        target
        / "plugins"
        / "cursor"
        / "endor-labs-agent-kit"
        / ".cursor-plugin"
        / "plugin.json"
    ).read_bytes() == first_cursor_manifest
    assert validate_marketplace_host_boundaries(target) == []


def test_marketplace_validator_rejects_cursor_agent_exposure_at_claude_root(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")
    sync_distribution(source, target)
    _write(
        target / "agents" / "endor-findings-browser-agent.md",
        "---\nmodel: composer-2.5[fast=false]\n---\n",
    )

    errors = validate_marketplace_host_boundaries(target)

    assert "root agents must be byte-identical to canonical Claude agents" in errors


def test_claude_official_root_validator_rejects_root_cursor_defaults(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")
    sync_distribution(source, target)
    _write(target / ".mcp.json", "{}\n")
    _write(target / "skills" / "unexpected-cursor-skill" / "SKILL.md")

    errors = validate_marketplace_host_boundaries(target)

    assert "root .mcp.json would be auto-loaded by Claude and must be absent" in errors
    assert "root skills must contain only the canonical Claude setup skill" in errors


def test_marketplace_validator_rejects_root_cursor_manifest_and_wrong_source(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")
    sync_distribution(source, target)
    _write(target / ".cursor-plugin" / "plugin.json", '{"name":"endorlabs"}\n')
    marketplace_path = target / ".cursor-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace["plugins"][0]["source"] = "./"
    marketplace_path.write_text(json.dumps(marketplace), encoding="utf-8")

    errors = validate_marketplace_host_boundaries(target)

    assert "root Cursor plugin.json must be absent in the multi-plugin mirror" in errors
    assert (
        "Cursor marketplace source must be ./plugins/cursor/endor-labs-agent-kit"
        in errors
    )


def test_sync_distribution_dry_run_does_not_modify_target(tmp_path):
    source = tmp_path / "agent-kit"
    target = tmp_path / "ai-plugins"
    source.mkdir()
    target.mkdir()
    _minimal_source_tree(source)
    _write(target / "README.md", "Current generated Agent Kit package version: `0.0.1`.\n")

    operations = sync_distribution(source, target, dry_run=True)

    assert operations
    assert not (target / "plugins").exists()
    assert "package version: `0.0.1`" in (target / "README.md").read_text(encoding="utf-8")
