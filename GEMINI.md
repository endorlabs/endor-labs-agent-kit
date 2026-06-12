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
- Diagnose Endor setup and scan issues: use skill `endor-troubleshooter`.
- Browse existing Endor findings: use skill `findings-browser`.
- Malware Response: use skill `malware-response`.
- Assess GitHub onboarding gaps: use skill `probe-droid`.
- Find safe SCA remediation paths: use skill `sca-remediation`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, collect/write API secrets, or
configure Endor MCP without explicit user approval.
