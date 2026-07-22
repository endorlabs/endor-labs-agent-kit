from __future__ import annotations

from pathlib import Path

from scripts.sync_ai_plugins_distribution import (
    generated_root_skills,
    sync_distribution,
)


def _write(path: Path, content: str = "content\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_source_tree(root: Path) -> None:
    for directory in ("plugins", ".cursor-plugin", "agents", "cursor-sdk", "hooks"):
        _write(root / directory / "artifact.txt")
    _write(root / "pyproject.toml", '[project]\nversion = "9.9.9"\n')
    _write(root / ".mcp.json", "{}\n")
    _write(root / "CHANGELOG.md", "# Changelog\n")
    _write(root / "GEMINI.md", "# Gemini\n")
    _write(root / ".claude-plugin" / "marketplace.json", "{}\n")
    _write(root / ".agents" / "plugins" / "marketplace.json", "{}\n")
    _write(root / "scripts" / "check_repository_hygiene.py", "# hygiene\n")
    _write(root / "scripts" / "validate_mirror_provenance.py", "# provenance\n")
    _write(root / "assets" / "logo.png", "<svg />\n")
    _write(root / "skills" / "configuration-automation" / "SKILL.md")
    _write(root / "skills" / "create-endor-labs-agent" / "SKILL.md")


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
    assert (target / "hooks" / "artifact.txt").read_text(encoding="utf-8") == "content\n"
    assert not (target / "hooks" / "stale-hook.sh").exists()
    assert (target / "skills" / "configuration-automation" / "SKILL.md").exists()
    assert not (target / "skills" / "create-endor-labs-agent").exists()
    assert not (target / "skills" / "old-generated-skill").exists()
    assert (target / ".mcp.json").read_text(encoding="utf-8") == "{}\n"
    assert (target / "CHANGELOG.md").read_text(encoding="utf-8") == "# Changelog\n"
    assert (target / "GEMINI.md").read_text(encoding="utf-8") == "# Gemini\n"
    assert (target / ".claude-plugin" / "marketplace.json").exists()
    assert (target / ".agents" / "plugins" / "marketplace.json").exists()
    assert (target / "scripts" / "check_repository_hygiene.py").exists()
    assert (target / "scripts" / "validate_mirror_provenance.py").exists()
    assert (target / "assets" / "logo.png").exists()
    assert not (target / "assets" / "logo.svg").exists()
    assert not (target / "gemini-extension.json").exists()
    assert "package version: `9.9.9`" in (target / "README.md").read_text(encoding="utf-8")
    assert any("sync" in operation for operation in operations)
    assert any("package version -> 9.9.9" in operation for operation in operations)
    assert any("gemini-extension.json" in operation for operation in operations)


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
