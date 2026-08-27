"""Tolerant coercion helpers shared by SCA contract validators."""

from __future__ import annotations

import json
import re
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(value, sort_keys=True)
        except (TypeError, ValueError, RecursionError):
            # str()/repr() would recurse on the same pathological nesting, so
            # fall back to a placeholder that can never match a contract token.
            return f"<unserializable:{type(value).__name__}>"
    return str(value).strip()


def _one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _int(value: Any) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if not _is_empty(value):
            return value
    return None
