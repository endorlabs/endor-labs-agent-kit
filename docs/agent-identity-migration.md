# Agent Identity Migration

This release exposes 11 canonical agents. Generated host artifacts, invocation
names, Agent API attribution, and new stored references use the canonical
identifier. Catalog wire schema v2 publishes `legacy_ids` so the Endor backend
can resolve an existing identifier without showing a duplicate agent.

## Canonical Catalog

| Display name | Canonical workflow id | Cursor or custom-agent id | Legacy workflow ids |
| --- | --- | --- | --- |
| AI SAST Remediation | `ai-sast-remediation` | `endor-ai-sast-remediation-agent` | `ai-sast-triage` |
| CI/CD And Supply Chain Posture | `cicd-posture` | `endor-cicd-posture-agent` | none |
| Configuration Automation | `configuration-automation` | `endor-configuration-automation-agent` | `probe-droid` |
| Dependency Reviewer | `dependency-reviewer` | `endor-dependency-reviewer-agent` | `dependency-decision-helper`, `package-risk-summary`, `repository-dependency-reviewer` |
| Findings Browser | `findings-browser` | `endor-findings-browser-agent` | none |
| Malware Responder | `malware-responder` | `endor-malware-responder-agent` | `malware-response` |
| OSS Upgrade Investigator | `oss-upgrade-investigator` | `endor-oss-upgrade-investigator-agent` | `upgrade-impact-analysis` |
| Remediation Planning | `remediation-planning` | `endor-remediation-planning-agent` | `remediation-planner` |
| SCA Remediation | `sca-remediation` | `endor-sca-remediation-agent` | none |
| Troubleshooting | `troubleshooting` | `endor-troubleshooting-agent` | `endor-troubleshooter` |
| Vulnerability Explainer | `vulnerability-explainer` | `endor-vulnerability-explainer-agent` | none; workflow id is unchanged |

Dependency Reviewer replaces three overlapping catalog entries. It chooses one
profile at the start of a run:

- `package-decision` for an adoption, upgrade, approval, or keep/avoid decision
- `package-risk` for an evidence-backed risk summary of one exact version
- `repository-review` for bounded local manifest and dependency inspection

The profiles are not separate public agents and must not call one another.

## Rollout Contract

1. Deploy backend support for catalog wire schema v2 and `legacy_ids`.
2. Verify every legacy id resolves to exactly one canonical id and the backend
   shows only the 11 canonical agents.
3. Publish and sign the regenerated Agent Kit catalog.
4. Sync the generated `ai-plugins` mirror and validate byte parity.
5. Verify fresh host installs and `endorctl agent api --agent-id ...` telemetry
   use canonical ids.
6. Monitor alias resolution and unknown-agent errors before removing any
   backend compatibility path.

Do not publish generated legacy agents beside the canonical agents. If backend
alias support is not ready, hold the catalog release; the source change can
remain unreleased. A rollback restores the previous generated catalog while
keeping backend alias support additive.

Saved prompts or automation should be updated to canonical identifiers. The
backend alias is a compatibility bridge, not the preferred identifier for new
calls.
