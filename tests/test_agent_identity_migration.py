from __future__ import annotations

import yaml

from endor_agent_kit.recipe import load_recipe

from conftest import repo_root


EXPECTED_IDENTITIES = {
    "ai-sast-remediation": ("AI SAST Remediation", ("ai-sast-triage",)),
    "cicd-posture": ("CI/CD And Supply Chain Posture", ()),
    "configuration-automation": ("Configuration Automation", ("probe-droid",)),
    "dependency-reviewer": (
        "Dependency Reviewer",
        (
            "dependency-decision-helper",
            "package-risk-summary",
            "repository-dependency-reviewer",
        ),
    ),
    "findings-browser": ("Findings Browser", ()),
    "malware-responder": ("Malware Responder", ("malware-response",)),
    "oss-upgrade-investigator": ("OSS Upgrade Investigator", ("upgrade-impact-analysis",)),
    "remediation-planning": ("Remediation Planning", ("remediation-planner",)),
    "sca-remediation": ("SCA Remediation", ()),
    "troubleshooting": ("Troubleshooting", ("endor-troubleshooter",)),
    "vulnerability-explainer": ("Vulnerability Explainer", ()),
}

CUSTOMER_SURFACE_ROOTS = (
    "agents",
    "skills",
    "cursor-sdk/agents",
    "claude-code",
    "claude-managed-agents",
    "codex",
    "gemini",
    "portable",
    "plugins",
)
CUSTOMER_TEXT_SUFFIXES = frozenset({".md", ".svg", ".yaml", ".json", ".toml"})
RETIRED_CUSTOMER_NAMES = (
    "AI SAST Triage",
    "Remediation Planner",
    "Dependency Decision Helper",
    "Repository Dependency Reviewer",
    "Endor Labs Vulnerability Explainer",
    "Endor Troubleshooter",
    "Probe Droid",
    "Malware Response",
    "Oss Upgrade Investigator",
)


def test_source_catalog_exposes_only_the_eleven_canonical_agent_identities():
    source_root = repo_root() / "source" / "agents"
    recipes = {
        path.parent.name: load_recipe(path)
        for path in sorted(source_root.glob("*/recipe.yaml"))
    }

    assert set(recipes) == set(EXPECTED_IDENTITIES)
    for agent_id, (name, legacy_ids) in EXPECTED_IDENTITIES.items():
        recipe = recipes[agent_id]
        assert recipe.id == agent_id
        assert recipe.name == name
        assert recipe.legacy_ids == legacy_ids


def test_legacy_agent_ids_have_one_canonical_owner_and_are_not_active_ids():
    aliases = {
        legacy_id: recipe_id
        for recipe_id, (_, legacy_ids) in EXPECTED_IDENTITIES.items()
        for legacy_id in legacy_ids
    }

    assert len(aliases) == 9
    assert not set(aliases) & set(EXPECTED_IDENTITIES)
    assert len(aliases) == sum(
        len(legacy_ids) for _, legacy_ids in EXPECTED_IDENTITIES.values()
    )


def test_root_customer_guides_use_every_canonical_display_name():
    root = repo_root()

    for path in (root / "README.md", root / "GEMINI.md"):
        text = path.read_text(encoding="utf-8")
        for display_name, _ in EXPECTED_IDENTITIES.values():
            assert display_name in text, f"{path.name} is missing {display_name!r}"


def test_customer_artifacts_do_not_publish_retired_names_or_identifiers():
    root = repo_root()
    legacy_ids = {
        legacy_id
        for _, legacy_ids in EXPECTED_IDENTITIES.values()
        for legacy_id in legacy_ids
    }
    paths = [root / "README.md", root / "GEMINI.md"] + [
        path
        for relative_root in CUSTOMER_SURFACE_ROOTS
        for path in (root / relative_root).rglob("*")
        if path.is_file() and path.suffix in CUSTOMER_TEXT_SUFFIXES
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for retired_name in RETIRED_CUSTOMER_NAMES:
            assert retired_name not in text, f"{path.relative_to(root)} publishes {retired_name!r}"
        for legacy_id in legacy_ids:
            assert legacy_id not in text, f"{path.relative_to(root)} publishes legacy id {legacy_id!r}"


def test_eval_cases_use_canonical_source_agent_ids():
    root = repo_root()
    retired_ids = {"ai_sast_triage", "remediation_planner"}

    for agent_id in EXPECTED_IDENTITIES:
        path = root / "source" / "agents" / agent_id / "evals" / "cases.yaml"
        if not path.exists():
            continue
        cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
        for case in cases:
            source_agent_id = case.get("input", {}).get("source_agent_id")
            assert source_agent_id not in retired_ids


def test_source_architecture_titles_use_canonical_display_names():
    root = repo_root()
    for agent_id, (display_name, _) in EXPECTED_IDENTITIES.items():
        architecture = root / "source" / "agents" / agent_id / "architecture.svg"
        if not architecture.exists():
            continue
        assert display_name in architecture.read_text(encoding="utf-8")
