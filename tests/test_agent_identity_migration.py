from __future__ import annotations

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
