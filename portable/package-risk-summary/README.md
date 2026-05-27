# Endor Labs Package Risk Summary Portable Agent Bundle

Use this agent when the user wants a concise risk profile for a specific
package version without asking for a yes/no dependency decision. Examples:
"Summarize npm lodash 4.17.20 risk", "Give me the risk picture for
log4j-core 2.14.1", "What should I know about this package version before I
review it?" Returns an evidence-backed package risk summary with
vulnerabilities, malware or typosquat signals, package scores, license notes,
recommended next checks, and any data gaps.

## Use This When

Use this bundle when your organization already has an agent runtime, source-provider workflow, ticketing workflow, approval system, credential controls, and audit pipeline. The bundle supplies the generated agent and runtime contract; your platform supplies adapters.

## Bundle Files

- `agent.md`: generated runtime-neutral agent instructions.
- `agent.manifest.json`: machine-readable runtime contract.
- `output-contract.md`: inputs, outputs, adapter contract summary, and workflow gates.
- `endorctl-setup.md`: Endor runtime setup notes.

## Runtime Responsibilities

- Load `agent.md` as generated instructions without editing it.
- Read `agent.manifest.json` to discover required transports, capabilities, declared actions, and runtime wrappers.
- Provide Endor MCP or Endor API transports declared by the manifest.
- Provide repository, source-provider, approval, ticketing, and Endor write adapters only when authorized by your platform policy.
- Pause for confirmation before any action where `confirmation_required` is true.
- Return structured evidence after adapter execution, or return a data gap when the adapter, credential, permission, or transport is unavailable.

## Security Model

Agent Kit defines the workflow, safety contract, and evidence requirements. Your runtime enforces tenant access, repository permissions, ticket or change-request permissions, approval policy, logging, audit, and adapter authorization. The agent must not improvise around missing permissions; the runtime should return a structured data gap instead.

## Example Adapter Mappings

These examples are illustrative, not requirements.

| Portable action | Example runtime adapters |
| --- | --- |
| `endor.query` | Endor API proxy, `endorctl api`, approved Endor MCP adapter |
| `source.change_request.create` | GitHub pull request, GitLab merge request, Bitbucket pull request, internal change workflow |
| `ticket.create` | Jira issue, ServiceNow task, Linear issue, internal ticketing |
| `approval.verify` | AppSec approval service, source-provider approval API, internal risk-acceptance workflow |
| `endor.policy.write` | Endor API proxy, approved policy-write service |

## Example Runtime Invocation

```text
System:
Load portable/<agent>/agent.md as the generated instruction source.
Expose only the adapters allowed by portable/<agent>/agent.manifest.json and your organization policy.
When the agent requests an action, pause for approval if confirmation_required=true.
After execution, return adapter evidence to the agent.

User:
Use this agent to analyze repository <repo>. Prefer ticket creation over a source change request unless the plan is low risk and validation evidence is available.
```

## Workflow Target Guidance

For remediation workflows, let the agent produce the remediation plan first. At the mutation gate, your runtime can offer approved targets such as plan-only output, source change request creation, ticket creation, or both. `ticket.create` is available as a runtime wrapper in portable bundles unless a recipe explicitly declares ticket creation as an agent-owned action.

## Drift Check

After copying this bundle into your runtime, compare it with the catalog manifest:

```bash
endor-agent-kit check-install --host portable --agent package-risk-summary --portable-dir /path/to/runtime/agents/package-risk-summary
```

## Generated Artifact Policy

`agent.md` and sibling contract files are generated. Configure runtime adapters and organization policy outside this bundle. If agent behavior must change, update the Source Recipe and regenerate the catalog.
