"""Deterministic router (P2): question -> OSS tool calls -> answer."""

from __future__ import annotations

from service.oss.mock import OssMockClient
from service.oss.router import RuleBasedRouter

router = RuleBasedRouter(OssMockClient())


def test_cve_question_routes_to_vulnerability_details():
    a = router.answer("What is CVE-2021-44228 and how bad is it?")
    assert a.tools_used == ["vulnerability_details"]
    assert a.advisory is not None and a.advisory.severity == "CRITICAL"
    assert "CVE-2021-44228" in a.answer and "CRITICAL" in a.answer


def test_package_question_routes_to_dependency_and_risk():
    a = router.answer("Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?")
    assert "dependency_vulnerabilities" in a.tools_used
    assert a.dependency is not None
    assert "log4j-core" in a.answer


def test_risk_wording_pulls_package_risk():
    a = router.answer("What's the risk score for npm://lodash@4.17.20?")
    assert "package_risk" in a.tools_used
    assert a.risk is not None and a.risk.scores


def test_upgrade_intent_pulls_recommend_upgrades():
    a = router.answer(
        "How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?"
    )
    assert "recommend_upgrades" in a.tools_used
    assert a.upgrades is not None and a.upgrades.options
    assert "Recommended upgrade" in a.answer


def test_no_upgrade_intent_skips_recommend_upgrades():
    a = router.answer("Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?")
    assert "recommend_upgrades" not in a.tools_used
    assert a.upgrades is None


def test_advisory_and_package_together():
    a = router.answer(
        "Does mvn://org.apache.logging.log4j:log4j-core@2.14.1 have CVE-2021-44228?"
    )
    assert "vulnerability_details" in a.tools_used
    assert "dependency_vulnerabilities" in a.tools_used
    assert a.advisory is not None and a.dependency is not None


def test_no_identifier_returns_guidance_data_gap():
    a = router.answer("Hello, can you help me with security stuff?")
    assert a.tools_used == []
    assert "no_package_or_advisory_identified" in a.data_gaps
    assert "CVE-2021-44228" in a.answer  # guidance names a concrete example


def test_unknown_cve_is_reported_not_invented():
    a = router.answer("Tell me about CVE-2000-0001")
    assert a.advisory is not None and a.advisory.found is False
    assert "no details found" in a.answer
