# Endor Labs Agent Kit Root Package

This repository root is a multi-host distribution surface, not a
Gemini CLI extension root. Do not install the repository root as a
Gemini extension.

Install Gemini CLI from `plugins/gemini/endor-labs-agent-kit/` so
Gemini discovers the generated Gemini skills from that extension's
`skills/` directory. Do not load the root Cursor skills as Gemini
workflows.

Use Endor Labs Agent Kit workflows only within their generated safety
contracts. Prefer documented Endor API or `endorctl api` lookups when a
workflow supports them. Use Endor MCP only when a selected MCP-capable
workflow needs it or the user explicitly asks for it.

If setup, authentication, namespace, Endor MCP, `endorctl`, `gh`, or
repository tooling is missing, use the `endor-agent-kit-setup` skill
before live Endor work.

User jobs mapped to root skills:

- Triage AI SAST findings: use skill `ai-sast-triage`.
- Assess CI/CD and supply chain posture: use skill `cicd-posture`.
- Dependency Decision Helper: use skill `dependency-decision-helper`.
- Diagnose Endor setup and scan issues: use skill `endor-troubleshooter`.
- Browse existing Endor findings: use skill `findings-browser`.
- Malware Response: use skill `malware-response`.
- Package Risk Summary: use skill `package-risk-summary`.
- Assess GitHub onboarding gaps: use skill `probe-droid`.
- Remediation Planner: use skill `remediation-planner`.
- Repository Dependency Reviewer: use skill `repository-dependency-reviewer`.
- Find safe SCA remediation paths: use skill `sca-remediation`.
- Upgrade Impact Analysis: use skill `upgrade-impact-analysis`.
- Vulnerability Explainer: use skill `vulnerability-explainer`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, collect/write API secrets, or
configure Endor MCP without explicit user approval.
