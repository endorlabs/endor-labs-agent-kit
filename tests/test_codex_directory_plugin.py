from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from conftest import GeneratedCatalog, repo_root
from endor_agent_kit.catalog_schema import CatalogPluginPackage
from endor_agent_kit.prepared_source_recipe import prepare_source_recipe
from endor_agent_kit.publication.codex_directory_plugin import (
    CODEX_DIRECTORY_CHANNEL,
    CODEX_DIRECTORY_PACKAGE_ROOT,
    CODEX_DIRECTORY_SKILL_IDS,
    publish_codex_directory_plugin_package,
)
from endor_agent_kit.publication.coordinator import HostArtifactPublication
from endor_agent_kit.publisher import publish_recipes
from scripts.build_codex_directory_submission import build_archive, validate_package


pytestmark = pytest.mark.publication


def _package(root: Path) -> Path:
    return root / CODEX_DIRECTORY_PACKAGE_ROOT


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_generated_catalog_contains_isolated_skills_only_codex_package(
    generated_catalog: GeneratedCatalog,
):
    package = _package(generated_catalog.root)

    assert {path.name for path in (package / "skills").iterdir()} == set(
        CODEX_DIRECTORY_SKILL_IDS
    )
    assert {path.name for path in package.iterdir()} == {
        ".codex-plugin",
        "assets",
        "skills",
    }
    assert not (package / "hooks").exists()
    assert not (package / "agents").exists()
    assert not (package / ".mcp.json").exists()
    assert not (package / ".app.json").exists()

    for skill_id in CODEX_DIRECTORY_SKILL_IDS:
        skill = package / "skills" / skill_id
        assert {
            path.relative_to(skill).as_posix()
            for path in skill.rglob("*")
            if path.is_file()
        } == {
            "SKILL.md",
            "agents/openai.yaml",
            "scripts/summarize_endor_artifact.py",
        }
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert f"endorctl agent api --agent-id {skill_id}" in text
        assert "$SKILL_DIR/scripts/summarize_endor_artifact.py" in text
        assert "python3 runtime/summarize_endor_artifact.py" not in text
        metadata = json.loads((skill / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        assert metadata["policy"] == {"allow_implicit_invocation": True}

    report = validate_package(generated_catalog.root)
    assert report["status"] == "passed"
    assert report["errors"] == []


def test_partial_publication_preserves_official_directory_and_manifest_record(
    tmp_path,
    generated_catalog: GeneratedCatalog,
):
    catalog = tmp_path / "catalog"
    shutil.copytree(generated_catalog.root, catalog)
    before_digest = _tree_digest(_package(catalog))
    before_manifest = json.loads((catalog / "manifest.json").read_text(encoding="utf-8"))
    before_record = next(
        package
        for package in before_manifest["plugin_packages"]
        if package["host"] == "codex"
        and package.get("distribution_channel", "repository") == CODEX_DIRECTORY_CHANNEL
    )

    publish_recipes(
        [repo_root() / "source" / "agents" / "findings-browser" / "recipe.yaml"],
        catalog,
        include_plugins=True,
    )

    after_manifest = json.loads((catalog / "manifest.json").read_text(encoding="utf-8"))
    after_record = next(
        package
        for package in after_manifest["plugin_packages"]
        if package["host"] == "codex"
        and package.get("distribution_channel", "repository") == CODEX_DIRECTORY_CHANNEL
    )
    assert after_record == before_record
    assert _tree_digest(_package(catalog)) == before_digest


def test_official_directory_publisher_rejects_noncanonical_codex_id(tmp_path):
    prepared = prepare_source_recipe(
        repo_root() / "source" / "agents" / "findings-browser" / "recipe.yaml"
    )
    unexpected = replace(
        prepared,
        recipe=replace(prepared.recipe, id="unexpected-workflow"),
    )

    with pytest.raises(ValueError, match="unexpected ids: unexpected-workflow"):
        publish_codex_directory_plugin_package((unexpected,), tmp_path)


def test_catalog_plugin_channels_round_trip_and_replace_independently(tmp_path):
    legacy = CatalogPluginPackage.from_manifest_record(
        {
            "host": "codex",
            "name": "endor-labs-agent-kit",
            "version": "1.0.0",
            "path": "plugins/codex/endor-labs-agent-kit",
            "included_agents": [],
            "artifacts": [],
        }
    )
    assert legacy.distribution_channel == "repository"

    official = CatalogPluginPackage(
        host="codex",
        name="endor-labs-agent-kit",
        version="1.0.0",
        path="plugins/codex-directory/endor-labs-agent-kit",
        included_agents=(),
        artifacts=(),
        distribution_channel="official-directory",
    )
    publication = HostArtifactPublication({})
    publication.write_plugin_packages(
        tmp_path,
        (legacy, official),
        replace_groups={("codex", "repository"), ("codex", "official-directory")},
    )
    replacement = CatalogPluginPackage(
        host="codex",
        name="endor-labs-agent-kit",
        version="2.0.0",
        path="plugins/codex/endor-labs-agent-kit",
        included_agents=(),
        artifacts=(),
    )
    publication.write_plugin_packages(
        tmp_path,
        (replacement,),
        replace_groups={("codex", "repository")},
    )

    packages = publication.catalog_plugin_packages(tmp_path)
    assert {
        (package.distribution_channel, package.version)
        for package in packages
    } == {("repository", "2.0.0"), ("official-directory", "1.0.0")}


def test_skill_local_helper_runs_once_from_unrelated_working_directory(
    tmp_path,
    generated_catalog: GeneratedCatalog,
):
    helper = (
        _package(generated_catalog.root)
        / "skills"
        / "findings-browser"
        / "scripts"
        / "summarize_endor_artifact.py"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    endorctl = bin_dir / "endorctl"
    invocation_log = tmp_path / "invocations.log"
    endorctl.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\n"
        "with open(os.environ['ENDOR_STUB_LOG'], 'a', encoding='utf-8') as handle:\n"
        "    handle.write('called\\n')\n"
        "print(json.dumps({'list': {'objects': [{'uuid': 'one'}, {'uuid': 'two'}]}}))\n",
        encoding="utf-8",
    )
    endorctl.chmod(0o755)
    unrelated = tmp_path / "unrelated-project"
    unrelated.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            str(helper.resolve()),
            "capture",
            "--",
            str(endorctl),
            "agent",
            "api",
            "--agent-id",
            "findings-browser",
            "list",
            "-r",
            "Finding",
            "--field-mask",
            "uuid",
            "-o",
            "json",
        ],
        cwd=unrelated,
        env={"ENDOR_STUB_LOG": str(invocation_log)},
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(completed.stdout)
    assert summary["status"] == "valid"
    assert summary["row_count"] == 2
    assert summary["unique_count"] == 2
    assert summary["artifact_ref"]
    assert summary["sha256"]
    assert summary["bytes"] > 0
    assert invocation_log.read_text(encoding="utf-8").splitlines() == ["called"]


def test_submission_archive_is_deterministic_and_has_one_plugin_root(
    tmp_path,
    generated_catalog: GeneratedCatalog,
):
    first = build_archive(
        generated_catalog.root,
        tmp_path / "first",
        ai_plugins_sha="a" * 40,
        agent_kit_source_sha="b" * 40,
    )
    second = build_archive(
        generated_catalog.root,
        tmp_path / "second",
        ai_plugins_sha="a" * 40,
        agent_kit_source_sha="b" * 40,
    )
    first_archive, first_checksum, first_validation, first_attestation = first
    second_archive = second[0]

    assert hashlib.sha256(first_archive.read_bytes()).hexdigest() == hashlib.sha256(
        second_archive.read_bytes()
    ).hexdigest()
    assert first_checksum.read_text(encoding="utf-8").startswith(
        hashlib.sha256(first_archive.read_bytes()).hexdigest()
    )
    assert json.loads(first_validation.read_text(encoding="utf-8"))["status"] == "passed"
    attestation = json.loads(first_attestation.read_text(encoding="utf-8"))
    assert attestation["ai_plugins_sha"] == "a" * 40
    assert attestation["agent_kit_source_sha"] == "b" * 40
    with zipfile.ZipFile(first_archive) as bundle:
        names = bundle.namelist()
        assert names
        assert all(name.startswith("endor-labs-agent-kit/") for name in names)
        assert all(".." not in Path(name).parts for name in names)
