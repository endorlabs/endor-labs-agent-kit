from __future__ import annotations

import json
from pathlib import Path

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.guardrails import check_catalog_guardrails
from endor_agent_kit.provenance import (
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    build_provenance_statement,
    file_sha256,
    verify_catalog_provenance,
)


def _write_min_catalog(
    root: Path,
    *,
    artifact_content: str = "agent body\n",
    recorded_sha: str | None = None,
) -> Path:
    bundle = root / "portable" / "demo"
    bundle.mkdir(parents=True)
    artifact = bundle / "agent.md"
    artifact.write_text(artifact_content, encoding="utf-8")
    sha = recorded_sha if recorded_sha is not None else file_sha256(artifact)
    manifest = {
        "schema_version": 1,
        "generated_by": "endor-agent-kit",
        "agents": [
            {
                "id": "demo",
                "host": "portable",
                "name": "Demo",
                "version": "0.1.0",
                "source": {
                    "recipe_schema_version": 1,
                    "builder_recipe": "source/agents/demo/recipe.yaml",
                },
                "editions": [
                    {
                        "id": "portable",
                        "name": "Portable",
                        "path": "portable/demo",
                        "artifacts": [
                            {
                                "path": "portable/demo/agent.md",
                                "sha256": sha,
                                "bytes": len(artifact_content.encode("utf-8")),
                            }
                        ],
                    }
                ],
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return artifact


def test_real_catalog_provenance_verifies():
    assert verify_catalog_provenance(repo_root()) == []


def test_verify_passes_for_consistent_catalog(tmp_path):
    _write_min_catalog(tmp_path)

    assert verify_catalog_provenance(tmp_path) == []


def test_verify_detects_tampered_artifact(tmp_path):
    _write_min_catalog(tmp_path, recorded_sha="0" * 64)

    errors = verify_catalog_provenance(tmp_path)

    assert any("sha256 mismatch" in error for error in errors)


def test_verify_detects_missing_artifact(tmp_path):
    artifact = _write_min_catalog(tmp_path)
    artifact.unlink()

    errors = verify_catalog_provenance(tmp_path)

    assert any("missing published artifact" in error for error in errors)


def test_verify_reports_missing_manifest(tmp_path):
    errors = verify_catalog_provenance(tmp_path)

    assert any("missing catalog manifest" in error for error in errors)


def test_statement_subject_anchors_manifest_and_is_deterministic(tmp_path):
    _write_min_catalog(tmp_path)

    statement = build_provenance_statement(tmp_path)

    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    subject = statement["subject"][0]
    assert subject["name"] == "manifest.json"
    assert subject["digest"]["sha256"] == file_sha256(tmp_path / "manifest.json")
    assert statement["predicate"]["catalog"] == [
        {
            "id": "demo",
            "host": "portable",
            "bundles": 1,
            "source_recipe": "source/agents/demo/recipe.yaml",
        }
    ]
    # Deterministic: no timestamp, reproducible from catalog content.
    assert build_provenance_statement(tmp_path) == statement


def test_check_guardrails_flags_provenance_drift(tmp_path):
    _write_min_catalog(tmp_path, recorded_sha="0" * 64)

    errors = check_catalog_guardrails(tmp_path)

    assert any("sha256 mismatch" in error for error in errors)


def test_verify_provenance_cli_round_trip(capsys):
    assert main(["verify-provenance", "--catalog-root", str(repo_root())]) == 0
    assert "OK:" in capsys.readouterr().out


def test_provenance_statement_cli_emits_valid_json(capsys):
    status = main(["provenance-statement", "--catalog-root", str(repo_root())])
    output = capsys.readouterr().out

    assert status == 0
    statement = json.loads(output)
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["subject"][0]["name"] == "manifest.json"


def test_provenance_statement_cli_writes_output_file(tmp_path):
    output = tmp_path / "statement.json"

    status = main(
        [
            "provenance-statement",
            "--catalog-root",
            str(repo_root()),
            "--output",
            str(output),
        ]
    )

    assert status == 0
    assert json.loads(output.read_text(encoding="utf-8"))["_type"] == STATEMENT_TYPE
