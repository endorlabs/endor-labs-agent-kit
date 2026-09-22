# Endor AURI Agent — Marketplace listing copy

Draft listing/description content for the Gemini Enterprise Marketplace submission.
Written to Endor Labs brand voice (evidence over claims, developer-first, no hype).

## Name
Endor AURI Agent

## One-line tagline
Find and fix vulnerable open-source dependencies from inside Gemini Enterprise.

## Short description (card / ~150 chars)
Ask about a CVE, check whether a package version is vulnerable, and get the exact upgrade that fixes it. Open-source intelligence from Endor Labs.

## Full description

Endor AURI Agent answers open-source software supply-chain questions inside Gemini
Enterprise. Ask about a CVE or GHSA advisory, check whether a specific package
version is vulnerable, review a dependency's risk, and get the exact upgrade that
resolves its known vulnerabilities.

When a package version is affected, the agent computes ranked upgrade options and
shows which advisories each version fixes and how large the jump is. For
`log4j-core@2.14.1`, it reports the Log4Shell chain (CVE-2021-44228,
CVE-2021-45046, CVE-2021-44832) and recommends 2.17.1, the smallest upgrade that
fixes all three.

Answers are read-only and come from Endor Labs' open-source intelligence, so
there is no login and no customer data involved. The agent runs on Vertex AI
Agent Engine and connects to Gemini Enterprise over A2A.

## What it does

- Vulnerability lookup: severity, CVSS and EPSS scores, summary, and fixed versions for a CVE or GHSA id.
- Dependency check: known vulnerabilities for a specific package version (by purl, e.g. `mvn://org.apache.logging.log4j:log4j-core@2.14.1`).
- Package risk: Endor risk scores for a package version.
- Upgrade recommendations: the versions that fix the known vulnerabilities, ranked, with the advisories each one resolves and whether the change is a patch, minor, or major jump.

## Who it's for
Developers and security engineers who need a fast, accurate answer on whether a
dependency is safe and what to upgrade to, without leaving their assistant.

## How it works
Built on the Google Agent Development Kit (ADK) and deployed to Vertex AI Agent
Engine. It registers with Gemini Enterprise as an A2A agent. The upgrade
recommendations are designed to render as interactive "pick an upgrade" choices
once A2UI is enabled.

## Notes for reviewers
- Data scope: public open-source intelligence only. No access to a customer's
  private projects or findings.
- Action scope: read-only. The agent explains and recommends; it does not modify
  code or open pull requests.
- Honesty: when the data has no answer, the agent says so rather than inventing a
  finding or a fix version.
