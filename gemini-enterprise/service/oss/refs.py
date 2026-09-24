"""Validation for OSS identifiers that flow into Endor filter expressions.

Same injection-safety discipline as the SCA path: an advisory id or purl is
interpolated into an Endor ``list_parameters.filter`` string, so it must be
pinned to an allowlist charset that cannot break out of the quoted literal.
"""

from __future__ import annotations

import re

from ..a2a.errors import InvalidParamsError

# CVE-YYYY-N+, GHSA-xxxx-xxxx-xxxx, or BIT-<slug>. No quotes/spaces.
ADVISORY_ID_RE = re.compile(
    r"^(?:CVE-\d{4}-\d{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|BIT-[A-Za-z0-9._-]+)$"
)
# A package URL: `scheme://name[@version]`. Charset excludes quotes and spaces.
PURL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[A-Za-z0-9._:@/+~-]+$")


def normalize_advisory_id(value: str) -> str:
    v = (value or "").strip().upper()
    if not ADVISORY_ID_RE.match(v):
        raise InvalidParamsError(
            "Invalid advisory id: expected a CVE, GHSA, or BIT identifier."
        )
    return v


def validate_purl(value: str) -> str:
    v = (value or "").strip()
    if not PURL_RE.match(v):
        raise InvalidParamsError(
            "Invalid package URL: expected e.g. 'mvn://group:artifact@1.2.3' or "
            "'npm://name@1.2.3'."
        )
    return v
