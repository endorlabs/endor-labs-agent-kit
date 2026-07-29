from __future__ import annotations

import json

import pytest

from endor_agent_kit.catalog_schema import CatalogAgent, CatalogArtifact, CatalogBundle
from endor_agent_kit.publication.catalog_wire import (
    CATALOG_PATH,
    CATALOG_SCHEMA_VERSION,
    catalog_wire_payload,
    stamp_catalog_version,
    write_catalog,
)


def _bundle(agent_id, host, edition_id, *, requires_endorctl=">=1.0.0"):
    path = f"{host}/{agent_id}"
    return CatalogBundle(
        agent_id=agent_id,
        agent_name="Agent Name",
        agent_version="1.0.0",
        host=host,
        bundle_id=edition_id,
        bundle_name=edition_id.replace("-", " ").title(),
        path=path,
        artifacts=(CatalogArtifact(path=f"{path}/{agent_id}.md", sha256="abc", bytes=1),),
        requires_endorctl=requires_endorctl,
    )


def _agent(
    agent_id,
    host,
    edition_id,
    *,
    audience="developer",
    category="Research & Investigate",
    requires_endorctl=">=1.0.0",
    legacy_ids=(),
):
    return CatalogAgent(
        id=agent_id,
        host=host,
        name="Agent Name",
        version="1.0.0",
        audience=audience,
        category=category,
        short_description="One-line pitch.",
        description="Long detail markdown.",
        authors=("Endor Labs",),
        requires_endorctl=requires_endorctl,
        legacy_ids=legacy_ids,
        editions=(_bundle(agent_id, host, edition_id, requires_endorctl=requires_endorctl),),
    )


def test_envelope_shape():
    payload = catalog_wire_payload([_agent("alpha-agent", "claude-code", "developer-edition")])

    assert payload["schema_version"] == CATALOG_SCHEMA_VERSION
    assert "catalog_version" not in payload
    assert "fetched_at" not in payload
    assert "stale" not in payload
    assert [agent["id"] for agent in payload["agents"]] == ["alpha-agent"]


def test_catalog_schema_is_v2_for_identity_aliases():
    assert CATALOG_SCHEMA_VERSION == "v2"


def test_catalog_version_stamped_when_provided():
    payload = catalog_wire_payload(
        [_agent("alpha-agent", "claude-code", "developer-edition")],
        catalog_version="agents-v1.0.0",
    )
    assert payload["catalog_version"] == "agents-v1.0.0"


def test_endor_agent_field_shape():
    payload = catalog_wire_payload([_agent("alpha-agent", "claude-code", "enterprise-edition")])
    agent = payload["agents"][0]

    assert agent == {
        "id": "alpha-agent",
        "name": "Agent Name",
        "audience": "developer",
        "category": "Research & Investigate",
        "short_description": "One-line pitch.",
        "description": "Long detail markdown.",
        "endorctl_min_version": "1.0.0",
        "version": "1.0.0",
        "authors": ["Endor Labs"],
        "install": [
            {
                "host": "claude-code",
                "command": (
                    "/plugin marketplace add endorlabs/ai-plugins\n"
                    "/plugin install endor-labs-agent-kit@endorlabs\n"
                    "/reload-plugins"
                ),
            }
        ],
    }


def test_endor_agent_emits_sorted_legacy_ids():
    payload = catalog_wire_payload(
        [
            _agent(
                "dependency-reviewer",
                "claude-code",
                "enterprise-edition",
                legacy_ids=("repository-dependency-reviewer", "dependency-decision-helper"),
            )
        ]
    )

    assert payload["agents"][0]["legacy_ids"] == [
        "dependency-decision-helper",
        "repository-dependency-reviewer",
    ]


def test_catalog_rejects_legacy_id_that_is_still_active():
    agents = [
        _agent(
            "dependency-reviewer",
            "claude-code",
            "enterprise-edition",
            legacy_ids=("package-risk-summary",),
        ),
        _agent("package-risk-summary", "claude-code", "enterprise-edition"),
    ]

    with pytest.raises(ValueError, match="active agent id"):
        catalog_wire_payload(agents)


def test_catalog_rejects_legacy_id_claimed_by_multiple_agents():
    agents = [
        _agent(
            "dependency-reviewer",
            "claude-code",
            "enterprise-edition",
            legacy_ids=("package-risk-summary",),
        ),
        _agent(
            "other-reviewer",
            "claude-code",
            "enterprise-edition",
            legacy_ids=("package-risk-summary",),
        ),
    ]

    with pytest.raises(ValueError, match="claimed by multiple"):
        catalog_wire_payload(agents)


def test_endorctl_min_version_strips_operator():
    payload = catalog_wire_payload(
        [_agent("alpha-agent", "claude-code", "developer-edition", requires_endorctl=">1.32.0")]
    )
    assert payload["agents"][0]["endorctl_min_version"] == "1.32.0"


def test_cadence_is_omitted():
    payload = catalog_wire_payload([_agent("alpha-agent", "claude-code", "developer-edition")])
    assert "cadence" not in payload["agents"][0]


def test_public_install_excludes_non_wire_hosts():
    agents = [
        _agent("alpha-agent", "claude-code", "enterprise-edition"),
        _agent("alpha-agent", "claude-managed-agents", "enterprise-edition"),
        _agent("alpha-agent", "gemini", "enterprise-edition"),
    ]
    payload = catalog_wire_payload(agents)
    install = payload["agents"][0]["install"]

    # Gemini is not a V1 wire install host. Claude Managed artifacts remain in
    # the repository but are intentionally not surfaced through the public UI.
    assert install == [
        {
            "host": "claude-code",
            "command": (
                "/plugin marketplace add endorlabs/ai-plugins\n"
                "/plugin install endor-labs-agent-kit@endorlabs\n"
                "/reload-plugins"
            ),
        },
    ]


def test_agents_sorted_by_id():
    agents = [
        _agent("zeta-agent", "claude-code", "developer-edition"),
        _agent("alpha-agent", "claude-code", "developer-edition"),
    ]
    payload = catalog_wire_payload(agents)
    assert [agent["id"] for agent in payload["agents"]] == ["alpha-agent", "zeta-agent"]


def test_agent_without_install_host_is_rejected():
    agents = [_agent("alpha-agent", "gemini", "enterprise-edition")]
    with pytest.raises(ValueError, match="install"):
        catalog_wire_payload(agents)


def test_audience_must_be_known():
    agents = [_agent("alpha-agent", "claude-code", "developer-edition", audience="platform")]
    with pytest.raises(ValueError, match="audience"):
        catalog_wire_payload(agents)


def test_published_agent_without_audience_raises():
    # A published agent (has editions) missing audience must fail loud, not vanish.
    agents = [_agent("legacy-agent", "claude-code", "developer-edition", audience="")]
    with pytest.raises(ValueError, match="audience"):
        catalog_wire_payload(agents)


def test_published_agent_without_category_raises():
    agents = [
        _agent(
            "legacy-agent",
            "claude-code",
            "developer-edition",
            category="",
        )
    ]
    with pytest.raises(ValueError, match="category"):
        catalog_wire_payload(agents)


def test_editionless_stub_is_skipped_not_emitted():
    # A manifest stub with no published editions (e.g. a hand-written merge record)
    # is excluded rather than crashing the catalog build.
    stub = CatalogAgent(id="stub-agent", host="claude-code", editions=())
    agents = [_agent("alpha-agent", "claude-code", "developer-edition"), stub]

    payload = catalog_wire_payload(agents)

    assert [agent["id"] for agent in payload["agents"]] == ["alpha-agent"]


def test_stamp_catalog_version_inserts_after_schema_version(tmp_path):
    catalog = write_catalog(tmp_path, [_agent("alpha-agent", "claude-code", "developer-edition")])
    assert "catalog_version" not in json.loads(catalog.read_text(encoding="utf-8"))

    stamp_catalog_version(catalog, "agents-v1.0.0")

    payload = json.loads(catalog.read_text(encoding="utf-8"))
    assert payload["catalog_version"] == "agents-v1.0.0"
    assert list(payload.keys())[:2] == ["schema_version", "catalog_version"]
    assert payload["agents"][0]["id"] == "alpha-agent"


def test_write_catalog_round_trips(tmp_path):
    written = write_catalog(tmp_path, [_agent("alpha-agent", "claude-code", "developer-edition")])

    assert written == tmp_path / CATALOG_PATH
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["agents"][0]["id"] == "alpha-agent"
    assert written.read_text(encoding="utf-8").endswith("\n")


def _claude_code_command(payload, agent_index=0):
    install = payload["agents"][agent_index]["install"]
    return next(entry["command"] for entry in install if entry["host"] == "claude-code")


def test_claude_code_install_uses_distribution_marketplace():
    payload = catalog_wire_payload([_agent("alpha-agent", "claude-code", "enterprise-edition")])
    command = _claude_code_command(payload)

    assert command == (
        "/plugin marketplace add endorlabs/ai-plugins\n"
        "/plugin install endor-labs-agent-kit@endorlabs\n"
        "/reload-plugins"
    )


def test_claude_code_install_never_references_a_repo_path():
    payload = catalog_wire_payload([_agent("alpha-agent", "claude-code", "enterprise-edition")])
    command = _claude_code_command(payload)

    assert "cp " not in command
    assert ".claude/agents" not in command
    assert "claude-code/alpha-agent" not in command
    # The source repo is only for hosts with no marketplace distribution, never claude-code.
    assert "git clone" not in command
    assert "endor-labs-agent-kit/claude" not in command


def test_claude_code_install_is_identical_across_agents():
    # The plugin brings every agent, so the command must not vary by agent id.
    payload = catalog_wire_payload(
        [
            _agent("alpha-agent", "claude-code", "enterprise-edition"),
            _agent("zeta-agent", "claude-code", "enterprise-edition"),
        ]
    )
    assert _claude_code_command(payload, 0) == _claude_code_command(payload, 1)


def test_claude_managed_only_agent_is_not_publicly_installable():
    agents = [_agent("alpha-agent", "claude-managed-agents", "enterprise-edition")]

    with pytest.raises(ValueError, match="no public install host"):
        catalog_wire_payload(agents)


def _install_by_host(payload, host, agent_index=0):
    install = payload["agents"][agent_index]["install"]
    return next(entry["command"] for entry in install if entry["host"] == host)


def test_agent_published_on_claude_code_and_codex_emits_both():
    agents = [
        _agent("alpha-agent", "claude-code", "enterprise-edition"),
        _agent("alpha-agent", "codex", "enterprise-edition"),
    ]
    install = catalog_wire_payload(agents)["agents"][0]["install"]

    # claude-code before codex, mirroring _WIRE_INSTALL_HOSTS order.
    assert [entry["host"] for entry in install] == ["claude-code", "codex"]


def test_codex_install_uses_distribution_marketplace_and_plugin_add():
    payload = catalog_wire_payload([_agent("alpha-agent", "codex", "enterprise-edition")])
    command = _install_by_host(payload, "codex")

    assert command == (
        "codex plugin marketplace add endorlabs/ai-plugins "
        "--ref {{catalog_version}} --sparse .agents "
        "--sparse plugins/codex/endor-labs-agent-kit\n"
        "codex plugin add endor-labs-agent-kit@endor-labs-agent-kit"
    )


def test_codex_install_is_identical_across_agents():
    payload = catalog_wire_payload(
        [
            _agent("alpha-agent", "codex", "enterprise-edition"),
            _agent("zeta-agent", "codex", "enterprise-edition"),
        ]
    )
    assert _install_by_host(payload, "codex", 0) == _install_by_host(payload, "codex", 1)


def test_stamp_resolves_codex_ref_placeholder(tmp_path):
    catalog = write_catalog(tmp_path, [_agent("alpha-agent", "codex", "enterprise-edition")])
    assert "{{catalog_version}}" in json.loads(catalog.read_text(encoding="utf-8"))[
        "agents"
    ][0]["install"][0]["command"]

    stamp_catalog_version(catalog, "agents-v1.1.0")

    command = json.loads(catalog.read_text(encoding="utf-8"))["agents"][0]["install"][0][
        "command"
    ]
    assert "{{catalog_version}}" not in command
    assert "--ref agents-v1.1.0 " in command


def test_stamp_leaves_placeholderless_commands_untouched(tmp_path):
    catalog = write_catalog(tmp_path, [_agent("alpha-agent", "claude-code", "enterprise-edition")])
    before = json.loads(catalog.read_text(encoding="utf-8"))["agents"][0]["install"][0]["command"]

    stamp_catalog_version(catalog, "agents-v1.1.0")

    after = json.loads(catalog.read_text(encoding="utf-8"))["agents"][0]["install"][0]["command"]
    assert after == before
