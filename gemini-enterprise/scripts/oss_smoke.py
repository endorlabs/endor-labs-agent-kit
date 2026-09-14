#!/usr/bin/env python3
"""Live proof of the three Option-A OSS tools against Endor's public `oss` data.

Uses Endor's own service credential (api-key stand-in) -- no customer tenant, no
per-user identity, exactly Option A.

Usage:
    ENDOR_ALLOW_ENDORCTL_CONFIG=1 python scripts/oss_smoke.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    import httpx

    from service.endor_client.auth import TokenProvider, load_credentials
    from service.oss.client import OssRestClient

    creds = load_credentials()
    http = httpx.Client(base_url=creds.base_url, timeout=45.0)
    client = OssRestClient(TokenProvider(creds, client=http))

    purl = "mvn://org.apache.logging.log4j:log4j-core@2.14.1"

    print("== vulnerability_details(CVE-2021-44228) ==")
    v = client.vulnerability_details("CVE-2021-44228")
    print(f"  {v.id}  severity={v.severity} cvss={v.cvss_score} epss={v.epss_score}")
    print(f"  {v.summary}")

    print(f"\n== dependency_vulnerabilities({purl}) ==")
    d = client.dependency_vulnerabilities(purl)
    print(f"  package={d.package_name}  found={d.found}  count={len(d.vulnerabilities)}")
    for x in d.vulnerabilities[:5]:
        print(f"    [{x.severity}] {x.id}: {(x.summary or '')[:60]}")

    print(f"\n== package_risk({purl}) ==")
    r = client.package_risk(purl)
    print(f"  package={r.package_name}  found={r.found}  scores={len(r.scores)}")
    for k, val in list(r.scores.items())[:8]:
        print(f"    {k} = {val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
