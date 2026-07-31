# Endor Labs Agent Kit Root Package

This repository root is a multi-host distribution surface, not a
Gemini CLI extension root. Do not install the repository root as a
Gemini extension.

Install Gemini CLI from `plugins/gemini/endor-labs-agent-kit/` so
Gemini discovers the generated Gemini skills from that extension's
`skills/` directory. Do not load the root Cursor skills as Gemini
workflows.

Use Endor Labs Agent Kit workflows only within their generated safety
contracts. Prefer `endorctl agent api --agent-id <canonical-recipe-id>` lookups when a
workflow supports them. Use Endor MCP only when a selected MCP-capable
workflow needs it or the user explicitly asks for it.

If setup, authentication, namespace, Endor MCP, `endorctl`, `gh`, or
repository tooling is missing, use the `endor-agent-kit-setup` skill
before live Endor work.

User jobs mapped to root skills:

- AI SAST Remediation: use skill `ai-sast-remediation`.
- CI/CD And Supply Chain Posture: use skill `cicd-posture`.
- Configuration Automation: use skill `configuration-automation`.
- Dependency Reviewer: use skill `dependency-reviewer`.
- Findings Browser: use skill `findings-browser`.
- Malware Responder: use skill `malware-responder`.
- OSS Upgrade Investigator: use skill `oss-upgrade-investigator`.
- Remediation Planning: use skill `remediation-planning`.
- SCA Remediation: use skill `sca-remediation`.
- Troubleshooting: use skill `troubleshooting`.
- Vulnerability Explainer: use skill `vulnerability-explainer`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, collect/write API secrets, or
configure Endor MCP without explicit user approval.
