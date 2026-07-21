# Endor Labs Agent Kit For Gemini CLI

Use Endor Labs Agent Kit workflows only within their generated safety
contracts. If setup, authentication, namespace, Endor MCP, `endorctl`,
`gh`, or repository tooling is missing, use the `endor-agent-kit-setup`
skill before live Endor work.

User jobs mapped to installed workflows:

- Triage AI SAST findings: use skill `ai-sast-remediation` or subagent `@ai-sast-remediation`.
- Assess CI/CD and supply chain posture: use skill `cicd-posture` or subagent `@cicd-posture`.
- Assess GitHub onboarding gaps: use skill `configuration-automation` or subagent `@configuration-automation`.
- Dependency Reviewer: use skill `dependency-reviewer` or subagent `@dependency-reviewer`.
- Browse existing Endor findings: use skill `findings-browser` or subagent `@findings-browser`.
- Malware Responder: use skill `malware-responder` or subagent `@malware-responder`.
- Oss Upgrade Investigator: use skill `oss-upgrade-investigator` or subagent `@oss-upgrade-investigator`.
- Remediation Planning: use skill `remediation-planning` or subagent `@remediation-planning`.
- Find safe SCA remediation paths: use skill `sca-remediation` or subagent `@sca-remediation`.
- Diagnose Endor setup and scan issues: use skill `troubleshooting` or subagent `@troubleshooting`.
- Vulnerability Explainer: use skill `vulnerability-explainer` or subagent `@vulnerability-explainer`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, or collect/write API secrets.
