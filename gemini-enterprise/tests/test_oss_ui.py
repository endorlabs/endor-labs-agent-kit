"""The interactive "pick an upgrade" element and its A2A / AG-UI adapters."""

from __future__ import annotations

from service.oss.mock import OssMockClient
from service.oss.models import UpgradeRecommendations
from service.oss.ui import (
    A2UI_MIME,
    A2UI_SELECT_EVENT,
    ELEMENT_TYPE,
    build_upgrade_element,
    to_a2a_parts,
    to_a2ui_messages,
    to_a2ui_parts,
    to_ag_ui_events,
    ui_protocol,
)

PURL = "mvn://org.apache.logging.log4j:log4j-core@2.14.1"


def _recs() -> UpgradeRecommendations:
    return OssMockClient().recommend_upgrades(PURL)


def test_build_element_from_recommendations():
    el = build_upgrade_element(_recs())
    assert el is not None
    assert el.type == ELEMENT_TYPE
    assert el.current_version == "2.14.1"
    assert [c.version for c in el.choices] == ["2.15.0", "2.16.0", "2.17.1"]
    rec = [c for c in el.choices if c.recommended]
    assert len(rec) == 1 and rec[0].version == "2.17.1" and rec[0].fixes_all
    # The recommended option's label reads as fixing everything.
    assert "fixes all" in rec[0].label
    assert rec[0].id == "2.17.1"  # selection value the client sends back


def test_build_element_returns_none_when_nothing_to_choose():
    assert build_upgrade_element(UpgradeRecommendations(purl=PURL, found=False)) is None
    assert build_upgrade_element(
        UpgradeRecommendations(purl=PURL, options=[])
    ) is None


def test_to_a2a_parts_is_a_marked_data_part():
    el = build_upgrade_element(_recs())
    parts = to_a2a_parts(el)
    assert len(parts) == 1
    part = parts[0]
    assert part["kind"] == "data"
    assert part["metadata"] == {"endor/ui": ELEMENT_TYPE}
    assert part["data"]["type"] == ELEMENT_TYPE
    assert [c["version"] for c in part["data"]["choices"]] == ["2.15.0", "2.16.0", "2.17.1"]


def test_to_ag_ui_events_custom_event_only_without_run_ids():
    el = build_upgrade_element(_recs())
    events = to_ag_ui_events(el)
    assert len(events) == 1
    assert events[0]["type"] == "CUSTOM"
    assert events[0]["name"] == ELEMENT_TYPE
    assert events[0]["value"]["choices"][0]["version"] == "2.15.0"


def test_to_ag_ui_events_wraps_a_run_when_ids_given():
    el = build_upgrade_element(_recs())
    events = to_ag_ui_events(el, thread_id="ctx-1", run_id="task-1")
    assert [e["type"] for e in events] == ["RUN_STARTED", "CUSTOM", "RUN_FINISHED"]
    assert events[0]["threadId"] == "ctx-1" and events[0]["runId"] == "task-1"


def test_ui_protocol_env(monkeypatch):
    monkeypatch.delenv("OSS_UI_PROTOCOL", raising=False)
    assert ui_protocol() == "a2a"
    monkeypatch.setenv("OSS_UI_PROTOCOL", "AG_UI")
    assert ui_protocol() == "ag_ui"
    monkeypatch.setenv("OSS_UI_PROTOCOL", "A2UI")
    assert ui_protocol() == "a2ui"
    monkeypatch.setenv("OSS_UI_PROTOCOL", "both")
    assert ui_protocol() == "both"
    monkeypatch.setenv("OSS_UI_PROTOCOL", "nonsense")
    assert ui_protocol() == "a2a"  # unknown value falls back to the default


# -- A2UI (Gemini Enterprise interactive protocol) ----------------------------

def test_a2ui_messages_structure():
    el = build_upgrade_element(_recs())
    msgs = to_a2ui_messages(el)
    assert [next(iter(m.keys() - {"version"})) for m in msgs] == [
        "createSurface", "updateComponents", "updateDataModel",
    ]
    assert all(m["version"] == "v0.9" for m in msgs)
    create, comps, data = msgs
    assert create["createSurface"]["surfaceId"] == comps["updateComponents"]["surfaceId"]
    assert "basic_catalog" in create["createSurface"]["catalogId"]


def test_a2ui_components_have_templated_list_and_select_button():
    el = build_upgrade_element(_recs())
    comps = to_a2ui_messages(el)[1]["updateComponents"]["components"]
    by_id = {c["id"]: c for c in comps}
    # A templated list over the /options data path.
    assert by_id["options-list"]["component"] == "List"
    assert by_id["options-list"]["children"] == {"componentId": "option-card", "path": "/options"}
    # The button emits the select event with version + purl context.
    ev = by_id["opt-button"]["action"]["event"]
    assert ev["name"] == A2UI_SELECT_EVENT
    assert ev["context"] == {"version": {"path": "version"}, "purl": {"path": "purl"}}


def test_a2ui_data_model_carries_the_options():
    el = build_upgrade_element(_recs())
    value = to_a2ui_messages(el)[2]["updateDataModel"]["value"]
    assert [o["version"] for o in value["options"]] == ["2.15.0", "2.16.0", "2.17.1"]
    rec = value["options"][-1]
    assert rec["version"] == "2.17.1"
    assert "recommended" in rec["jump"] and rec["buttonLabel"] == "Upgrade to 2.17.1"
    assert rec["purl"] == el.purl and value["purl"] == el.purl


def test_a2ui_parts_are_tagged_datapart_messages():
    el = build_upgrade_element(_recs())
    parts = to_a2ui_parts(el)
    assert len(parts) == 3
    assert all(p["kind"] == "data" and p["metadata"]["mimeType"] == A2UI_MIME for p in parts)
    assert A2UI_MIME == "application/json+a2ui"
