# Codex Public Directory Submission Packet

Use this packet for the skills-only Endor Labs Agent Kit submission. It is a
release checklist and portal input template, not evidence that external access
or approval is complete.

## Artifact Contract

- Tracked mirror: `plugins/codex-directory/endor-labs-agent-kit/`
- Contents: exactly 11 canonical workflow skills, plugin metadata, square
  images, and one skill-local artifact summarizer per workflow
- Excludes: setup, installers, custom agents, hooks, MCP/apps, staging values,
  credentials, absolute user paths, and model pins
- Build source: one exact immutable `ai-plugins` SHA after mirror merge
- Workflow outputs: ZIP, SHA-256, validation report, and attestation
- Maximum upload: 100 MB with one plugin root

## Proposed Listing

- Name: Endor Labs Agent Kit
- Short description: Endor security workflows
- Developer: Endor Labs
- Category: Developer Tools
- Long description: Use eleven source-generated Endor Labs workflows to
  investigate, triage, plan, and remediate application security and software
  supply-chain risks from Codex.
- Starter prompts:
  1. Browse and summarize my active Endor findings.
  2. Investigate an Endor vulnerability and explain its impact.
  3. Plan a safe dependency remediation using Endor evidence.
- Release notes: Add the initial skills-only Codex distribution generated from
  the same canonical Agent Kit recipes as the CLI/custom-agent package.
- Regions: decide with Product and Legal immediately before submission.

Verify the current production website, support, privacy, and terms URLs in the
portal. Do not guess or copy staging/internal URLs into the artifact or listing.

## External Preflight

Record these in the release ticket or private release evidence, not in Git:

- exact OpenAI organization and project
- submitter has current Apps Management write access (or current equivalent)
- verified Endor Labs business/developer identity is visible to that project
- production website, support, privacy, and terms URLs are public and aligned
- reviewer credentials and fixtures work without MFA, VPN, email/SMS approval,
  or private-network access
- supported production `endorctl` version is installed and on PATH
- reviewer namespace is selected explicitly; `agent api --help` and one bounded
  attributed read succeed
- credential/config cleanup is proven after review

## Five Positive Cases

Replace fixture placeholders with reviewer-accessible production fixture values.

1. Findings browse: ask for active critical/high findings in `<namespace>`;
   expect Findings Browser, attributed bounded reads, explicit traversal choice,
   concise rows, pagination, and an evidence ledger.
2. Vulnerability explanation: provide `<finding-or-CVE>`; expect verified finding
   context, impact, exploitability, remediation guidance, and data gaps.
3. Dependency review: provide `<package>@<version>`; expect package risk,
   decision conditions, alternatives, license notes, and attributed evidence.
4. SCA plan-only remediation: provide `<repository>`; expect scope resolution,
   evidence-backed candidate selection, risk decision, validation plan, and no
   edits or PR until its explicit gate.
5. Configuration assessment: provide `<github-org-or-repo>`; expect read-only
   onboarding/coverage gaps, deterministic prescriptions, and no mutations.

For each case, capture the prompt, expected selected skill, expected result
shape, fixture identifiers, attributed-command ledger, and redacted proof.

## Three Negative Cases

1. Ask a read-only workflow to edit code or open a PR without approval; expect a
   refusal or future-action handoff and zero mutation calls.
2. Omit namespace when multiple configured sources conflict; expect a concise
   clarification and zero Endor calls until scope is selected.
3. Ask for complete raw cross-namespace rows without a justified completeness
   requirement; expect bounded results or clarification, not automatic
   `--list-all` expansion. If completeness is then explicit, expect one
   `--traverse` plus `--list-all` helper capture and compact artifact metadata.

## Submission Gate

Submit only when the current portal scan passes, all eight cases are reproducible,
the artifact digests match the immutable workflow proof, and Product/Security/
Legal approve the listing and regions. Code readiness and external portal
readiness must be reported separately.
