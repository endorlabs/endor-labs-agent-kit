"""Prompt compaction helpers for generated plugin packages."""

from __future__ import annotations

import re

COMPACT_OMIT_START = "<!-- compact-plugin:omit-start -->"
COMPACT_OMIT_END = "<!-- compact-plugin:omit-end -->"

_OMIT_BLOCK_RE = re.compile(
    rf"\n?{re.escape(COMPACT_OMIT_START)}\n.*?\n{re.escape(COMPACT_OMIT_END)}\n?",
    re.DOTALL,
)
_MARKER_LINE_RE = re.compile(
    rf"^\s*(?:{re.escape(COMPACT_OMIT_START)}|{re.escape(COMPACT_OMIT_END)})\s*$\n?",
    re.MULTILINE,
)


def compact_marked_sections(text: str) -> str:
    """Remove source-marked reference-only blocks from plugin prompts."""

    compacted = _OMIT_BLOCK_RE.sub("\n", text)
    return _collapse_blank_lines(compacted).strip() + "\n"


def strip_compaction_marker_lines(text: str) -> str:
    """Hide compaction markers while preserving full prompt content."""

    return _MARKER_LINE_RE.sub("", text)


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)
