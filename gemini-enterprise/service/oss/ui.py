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
    """Which interactive protocol to emit: ``a2a`` (default), ``ag_ui``, or ``both``."""

    value = os.environ.get("OSS_UI_PROTOCOL", "a2a").strip().lower()
    return value if value in ("a2a", "ag_ui", "both") else "a2a"
