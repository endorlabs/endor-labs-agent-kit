# Endor Labs Agent Kit For Gemini CLI

Use Endor Labs Agent Kit workflows only within their generated safety
contracts. If setup, authentication, namespace, Endor MCP, `endorctl`,
`gh`, or repository tooling is missing, use the `endor-agent-kit-setup`
skill before live Endor work.

User jobs mapped to installed workflows:

- Triage AI SAST findings: use skill `ai-sast-triage` or subagent `@ai-sast-triage`.
- Assess CI/CD and supply chain posture: use skill `cicd-posture` or subagent `@cicd-posture`.
- Dependency Decision Helper: use skill `dependency-decision-helper` or subagent `@dependency-decision-helper`.
- Diagnose Endor setup and scan issues: use skill `endor-troubleshooter` or subagent `@endor-troubleshooter`.
- Browse existing Endor findings: use skill `findings-browser` or subagent `@findings-browser`.
- Malware Response: use skill `malware-response` or subagent `@malware-response`.
- Package Risk Summary: use skill `package-risk-summary` or subagent `@package-risk-summary`.
- Assess GitHub onboarding gaps: use skill `probe-droid` or subagent `@probe-droid`.
- Remediation Planner: use skill `remediation-planner` or subagent `@remediation-planner`.
- Repository Dependency Reviewer: use skill `repository-dependency-reviewer` or subagent `@repository-dependency-reviewer`.
- Find safe SCA remediation paths: use skill `sca-remediation` or subagent `@sca-remediation`.
- Upgrade Impact Analysis: use skill `upgrade-impact-analysis` or subagent `@upgrade-impact-analysis`.
- Vulnerability Explainer: use skill `vulnerability-explainer` or subagent `@vulnerability-explainer`.

Setup must not run scans, run `endorctl host-check`, edit shell profiles,
auto-install `gh`, install language tooling, or collect/write API secrets.
