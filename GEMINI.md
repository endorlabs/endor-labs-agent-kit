# Endor Labs Agent Kit Root Package

Use Endor Labs Agent Kit workflows only within their generated safety
contracts. Prefer documented Endor API or `endorctl api` lookups when a
workflow supports them. Use Endor MCP only when a selected MCP-capable
workflow needs it or the user explicitly asks for it.

If setup, authentication, namespace, Endor MCP, `endorctl`, `gh`, or
repository tooling is missing, use the `endor-agent-kit-setup` skill
before live Endor work.

User jobs mapped to root skills:

- Triage AI SAST findings: use skill `ai-sast-triage`.
- Diagnose Endor setup and scan issues: use skill `endor-troubleshooter`.
- Malware Response: use skill `malware-response`.
- Assess GitHub onboarding gaps: use skill `probe-droid`.
- Find safe SCA remediation paths: use skill `sca-remediation`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, collect/write API secrets, or
configure Endor MCP without explicit user approval.
