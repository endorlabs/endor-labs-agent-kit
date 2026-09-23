"""Render upgrade recommendations as an interactive "pick an upgrade" element.

This is the emission layer Google CSE calls the "A2-UI" ask: the model's
:class:`UpgradeRecommendations` content is turned into *selectable* choices in
the wire format the Gemini Enterprise frontend renders. Which wire format that
is — **A2A** structured message parts or **AG-UI** events — is still an open
question for Google (see docs/progress-and-hosting-readiness.md, Q9), so this
module keeps one canonical element (:class:`UpgradeChoiceElement`) and offers
*both* adapters. The content layer stays the single source of truth; only the
adapter changes when Google confirms the protocol.

Select the emitted protocol with ``OSS_UI_PROTOCOL`` (``a2a`` default, ``ag_ui``,
or ``both``).
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from .models import UpgradeRecommendations

# Marker so a frontend can recognize our interactive element regardless of the
# surrounding transport.
ELEMENT_TYPE = "endor.upgrade_choices"

_JUMP_WORD = {
    "patch": "patch upgrade",
    "minor": "minor upgrade",
    "major": "major upgrade",
    "none": "no version change",
    "unknown": "upgrade",
}


class UpgradeChoice(BaseModel):
    """One selectable option in the interactive element."""

    id: str                       # selection value the client sends back (the version)
    version: str
    label: str                    # short, human-facing button/label text
    description: str              # one-line detail under the label
    fixes: list[str] = Field(default_factory=list)  # advisory ids this option resolves
    fixes_all: bool = False
    jump: str = "unknown"
    recommended: bool = False


class UpgradeChoiceElement(BaseModel):
    """Canonical, protocol-neutral interactive element.

    Adapters below serialize this to A2A parts or AG-UI events; nothing here is
    tied to a transport.
    """

    type: str = ELEMENT_TYPE
    purl: str
    package_name: str | None = None
    current_version: str | None = None
    total_vulnerabilities: int = 0  # count of known vulns (the "of N" denominator)
    prompt: str
    choices: list[UpgradeChoice] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


def _choice_label(version: str, fixes_count: int, total: int, jump: str, recommended: bool) -> str:
    scope = "fixes all" if fixes_count >= total and total > 0 else f"fixes {fixes_count} of {total}"
    label = f"Upgrade to {version} — {scope} ({_JUMP_WORD.get(jump, 'upgrade')})"
    return f"{label} · recommended" if recommended else label


def build_upgrade_element(recs: UpgradeRecommendations) -> UpgradeChoiceElement | None:
    """Turn recommendations into an interactive element, or None if there is
    nothing to choose (package not found, or no available fix)."""

    if not recs.found or not recs.options:
        return None

    total = len(recs.current_vulnerabilities)
    choices = [
        UpgradeChoice(
            id=opt.version,
            version=opt.version,
            label=_choice_label(opt.version, len(opt.fixes), total, opt.jump, opt.recommended),
            description=(
                f"Resolves {', '.join(opt.fixes)}."
                if opt.fixes
                else "No advisories resolved."
            ),
            fixes=list(opt.fixes),
            fixes_all=opt.fixes_all,
            jump=opt.jump,
            recommended=opt.recommended,
        )
        for opt in recs.options
    ]

    name = recs.package_name or recs.purl
    current = f" {recs.current_version}" if recs.current_version else ""
    prompt = f"Choose an upgrade for {name}{current} to fix its known vulnerabilities:"

    return UpgradeChoiceElement(
        purl=recs.purl,
        package_name=recs.package_name,
        current_version=recs.current_version,
        total_vulnerabilities=total,
        prompt=prompt,
        choices=choices,
        data_gaps=list(recs.data_gaps),
    )


# -- adapters -----------------------------------------------------------------

def to_a2a_parts(element: UpgradeChoiceElement) -> list[dict]:
    """A2A structured message parts: one ``DataPart`` carrying the element.

    The ``metadata`` marker lets a client detect the interactive element and
    render selectable choices instead of showing raw JSON. The user's selection
    comes back as a normal text/data message referencing the chosen ``id``.
    """

    return [
        {
            "kind": "data",
            "data": element.model_dump(mode="json"),
            "metadata": {"endor/ui": ELEMENT_TYPE},
        }
    ]


def to_ag_ui_events(
    element: UpgradeChoiceElement,
    *,
    thread_id: str | None = None,
    run_id: str | None = None,
) -> list[dict]:
    """AG-UI event stream: a minimal run carrying the element as a CUSTOM event.

    AG-UI's ``CUSTOM`` event is the standard escape hatch for app-specific
    interactive/generative UI; ``name`` identifies the element and ``value`` is
    the payload the renderer consumes. Wrapped in RUN_STARTED/RUN_FINISHED so it
    is a valid, self-contained stream.
    """

    events: list[dict] = []
    if thread_id is not None or run_id is not None:
        events.append({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
    events.append(
        {"type": "CUSTOM", "name": ELEMENT_TYPE, "value": element.model_dump(mode="json")}
    )
    if thread_id is not None or run_id is not None:
        events.append({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})
    return events


def ui_protocol() -> str:
    """Which interactive protocol to emit: ``a2a`` (default), ``ag_ui``, ``a2ui``, or ``both``."""

    value = os.environ.get("OSS_UI_PROTOCOL", "a2a").strip().lower()
    return value if value in ("a2a", "ag_ui", "a2ui", "both") else "a2a"


# -- A2UI (Gemini Enterprise's GA interactive-UI protocol) --------------------
# GE renders A2UI: the agent returns a JSON UI tree (Card/Text/Button/List/…)
# plus a data model, embedded in the A2A response as DataParts with mimeType
# ``application/json+a2ui``. The user's selection returns as a Button
# ``action.event`` (name + context) on the next turn. GE supports v0.9 and v0.8;
# we target v0.9 with the basic component catalog.

A2UI_MIME = "application/json+a2ui"
A2UI_VERSION = "v0.9"
A2UI_BASIC_CATALOG = "https://a2ui.org/specification/v0_9/basic_catalog.json"
A2UI_SURFACE_ID = "endor-upgrade-choices"
# Event GE sends back when the user picks an option; context carries the choice.
A2UI_SELECT_EVENT = "select_upgrade"


def _a2ui_components() -> list[dict]:
    """The component tree: a heading + a templated list of upgrade cards, each with
    a select button whose action.event returns the chosen version/purl."""

    return [
        {"id": "root", "component": "Column", "children": ["heading", "options-list"]},
        {"id": "heading", "component": "Text", "variant": "h2", "text": {"path": "/title"}},
        {
            "id": "options-list",
            "component": "List",
            "direction": "vertical",
            "children": {"componentId": "option-card", "path": "/options"},
        },
        {"id": "option-card", "component": "Card", "child": "option-col"},
        {
            "id": "option-col",
            "component": "Column",
            "children": ["opt-version", "opt-summary", "opt-jump", "opt-button-row"],
        },
        {"id": "opt-version", "component": "Text", "variant": "h3", "text": {"path": "version"}},
        {"id": "opt-summary", "component": "Text", "text": {"path": "summary"}},
        {"id": "opt-jump", "component": "Text", "variant": "caption", "text": {"path": "jump"}},
        {"id": "opt-button-row", "component": "Row", "justify": "end", "children": ["opt-button"]},
        {
            "id": "opt-button",
            "component": "Button",
            "variant": "primary",
            "child": "opt-button-text",
            "action": {
                "event": {
                    "name": A2UI_SELECT_EVENT,
                    "context": {"version": {"path": "version"}, "purl": {"path": "purl"}},
                }
            },
        },
        {"id": "opt-button-text", "component": "Text", "text": {"path": "buttonLabel"}},
    ]


def _a2ui_data_model(element: UpgradeChoiceElement) -> dict:
    name = element.package_name or element.purl
    current = f" {element.current_version}" if element.current_version else ""
    total = element.total_vulnerabilities or len(element.choices)
    options = []
    for c in element.choices:
        n = len(c.fixes)
        if n >= total and total > 0:
            scope = f"Fixes all {total} known vulnerabilities"
        else:
            shown = ", ".join(c.fixes[:4])
            more = f" +{n - 4} more" if n > 4 else ""
            scope = f"Fixes {n} of {total}: {shown}{more}"
        jump = f"{c.jump} upgrade" + (" · recommended" if c.recommended else "")
        options.append({
            "version": c.version,
            "purl": element.purl,
            "summary": scope,
            "jump": jump,
            "buttonLabel": f"Upgrade to {c.version}",
        })
    return {
        "title": f"Choose an upgrade for {name}{current}",
        "purl": element.purl,
        "options": options,
    }


def to_a2ui_messages(element: UpgradeChoiceElement) -> list[dict]:
    """The A2UI v0.9 message list: create the surface, send components, send data."""

    return [
        {
            "version": A2UI_VERSION,
            "createSurface": {"surfaceId": A2UI_SURFACE_ID, "catalogId": A2UI_BASIC_CATALOG},
        },
        {
            "version": A2UI_VERSION,
            "updateComponents": {"surfaceId": A2UI_SURFACE_ID, "components": _a2ui_components()},
        },
        {
            "version": A2UI_VERSION,
            "updateDataModel": {
                "surfaceId": A2UI_SURFACE_ID,
                "path": "/",
                "value": _a2ui_data_model(element),
            },
        },
    ]


def to_a2ui_parts(element: UpgradeChoiceElement) -> list[dict]:
    """Wrap each A2UI message as an A2A ``DataPart`` tagged with the A2UI mimeType."""

    return [
        {"kind": "data", "data": msg, "metadata": {"mimeType": A2UI_MIME}}
        for msg in to_a2ui_messages(element)
    ]


# -- Gemini Enterprise native suggestion chips --------------------------------
# GE renders a typed part (mimeType ``application/json+suggestions``) as clickable
# suggestion chips. We can piggy-back on that supported widget to surface the
# upgrade choices as interactive chips, since GE does not render arbitrary parts.

GE_SUGGESTIONS_MIME = "application/json+suggestions"


def to_ge_suggestion_questions(element: UpgradeChoiceElement) -> list[str]:
    """Phrase each upgrade option as a short, distinctive suggestion chip."""

    name = element.package_name or element.purl
    out: list[str] = []
    for c in element.choices:
        scope = "fixes all" if c.fixes_all else f"fixes {len(c.fixes)}"
        tag = " — recommended" if c.recommended else ""
        out.append(f"Upgrade {name} to {c.version} ({scope}, {c.jump}){tag}")
    return out


def to_ge_suggestions_payload(element: UpgradeChoiceElement) -> dict:
    """The GE ``application/json+suggestions`` body carrying our upgrade chips."""

    return {"recommendedQuestionsResponse": {"questions": to_ge_suggestion_questions(element)}}
