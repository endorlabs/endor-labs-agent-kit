# Amp MCP Setup

Use this guide to connect Endor Labs Agent Kit support context to
[Amp](https://ampcode.com/) through the Endor Labs MCP server. Amp does not
currently have a generated Agent Kit plugin package in this repository; this is
an MCP-only setup path for exposing Endor Labs tools to Amp.

## What This Enables

After setup, Amp can call the Endor Labs MCP server to:

- check a dependency version for known vulnerabilities
- check a dependency for broader package risk, including malware signals
- retrieve Endor vulnerability details
- run local repository scans for dependencies, secrets, SAST, AI SAST, and
  GitHub Actions risks, depending on account edition and scan options
- run Endor security review for local diffs when Enterprise Edition and AI
  security code review are enabled

The MCP server runs locally over stdio. Amp launches it as a tool server and the
server handles Endor authentication through `endorctl`.

## Prerequisites

- Amp CLI installed and signed in.
- Node.js and `npx` available, or a directly installed `endorctl` binary.
- For Enterprise Edition, an Endor Labs namespace and configured authentication
  mode.

## Developer Edition

Developer Edition uses Endor Labs default policies. It does not require a paid
Endor Labs namespace.

Add the MCP server to Amp global settings:

```bash
amp mcp add endor-cli-tools -- npx -y endorctl ai-tools mcp-server
```

Equivalent Amp settings JSON:

```json
{
  "amp.mcpServers": {
    "endor-cli-tools": {
      "command": "npx",
      "args": ["-y", "endorctl", "ai-tools", "mcp-server"]
    }
  }
}
```

Use `--workspace` when the configuration should be committed or reviewed as a
workspace-specific `.amp/settings.json` file instead of a user-wide setting:

```bash
amp mcp add --workspace endor-cli-tools -- npx -y endorctl ai-tools mcp-server
```

Workspace MCP servers require Amp workspace trust approval before they run.

## Enterprise Edition

Enterprise Edition connects Amp to an Endor Labs namespace so checks use the
organization's policies, permissions, and reporting context.

Example with SSO:

```bash
amp mcp add endor-cli-tools \
  --env ENDOR_NAMESPACE=your-namespace \
  --env ENDOR_MCP_SERVER_AUTH_MODE=sso \
  --env ENDOR_MCP_SERVER_AUTH_TENANT=your-tenant \
  -- npx -y endorctl ai-tools mcp-server
```

Example with GitHub authentication:

```bash
amp mcp add endor-cli-tools \
  --env ENDOR_NAMESPACE=your-namespace \
  --env ENDOR_MCP_SERVER_AUTH_MODE=github \
  -- npx -y endorctl ai-tools mcp-server
```

Equivalent Amp settings JSON:

```json
{
  "amp.mcpServers": {
    "endor-cli-tools": {
      "command": "npx",
      "args": ["-y", "endorctl", "ai-tools", "mcp-server"],
      "env": {
        "ENDOR_NAMESPACE": "your-namespace",
        "ENDOR_MCP_SERVER_AUTH_MODE": "sso",
        "ENDOR_MCP_SERVER_AUTH_TENANT": "your-tenant"
      }
    }
  }
}
```

For non-SSO Enterprise authentication, set `ENDOR_MCP_SERVER_AUTH_MODE` to the
organization-approved mode such as `github`, `gitlab`, or `google`, and omit
`ENDOR_MCP_SERVER_AUTH_TENANT` unless SSO requires it.

## Windows Direct-Binary Fallback

If `npx -y endorctl ...` downloads the package but Amp cannot start the MCP
server, install or locate `endorctl` and configure Amp to call the executable
directly.

Common Windows npm binary path:

```text
%APPDATA%\npm\bin\endorctl.exe
```

PowerShell example:

```powershell
amp mcp add endor-cli-tools -- "$env:APPDATA\npm\bin\endorctl.exe" ai-tools mcp-server
```

Equivalent settings JSON:

```json
{
  "amp.mcpServers": {
    "endor-cli-tools": {
      "command": "C:\\Users\\<user>\\AppData\\Roaming\\npm\\bin\\endorctl.exe",
      "args": ["ai-tools", "mcp-server"]
    }
  }
}
```

Use an absolute path in settings JSON because MCP command fields may not expand
shell variables.

## Verify The Integration

List configured MCP servers:

```bash
amp mcp list
```

Check server status:

```bash
amp mcp doctor
```

Then ask Amp to run a dependency check:

```text
Check if the npm package lodash version 4.17.20 has any vulnerabilities using Endor Labs.
```

Amp should call the Endor Labs MCP tool and return vulnerability status,
advisory identifiers, and a remediation recommendation when available.

## Optional Project Guidance

Add project-level guidance when you want Amp to use Endor Labs automatically for
specific workflows. For example, add the following to `AGENTS.md` in a
repository that uses Amp:

```markdown
# Endor Labs Security Workflow For Amp

This repository uses Endor Labs through the Amp MCP server `endor-cli-tools`.

When dependency manifests or lockfiles are created or modified:

- Use the Endor Labs MCP tool `check_dependency_for_vulnerabilities` for each
  added or changed dependency when the ecosystem, dependency name, and version
  are known.
- If a dependency is vulnerable, recommend or apply the smallest safe upgrade
  that satisfies the repository constraints.
- Re-check the dependency after remediation.

For security-sensitive code changes, consider the Endor Labs MCP `scan` tool
with the narrowest relevant scan types. Use `security_review` only when the
Endor Labs account edition and namespace are configured for AI security code
review.

Do not print, persist, or copy secret values. Report credential presence only
by variable or key name.
```

Keep the guidance scoped. Do not force a full scan after every edit unless the
project explicitly wants that latency and policy behavior.

## Troubleshooting

- If Amp cannot see the tools, restart the Amp session after adding the MCP
  server.
- If a workspace MCP server is awaiting approval, run
  `amp mcp approve endor-cli-tools` from the workspace.
- If `npx` times out or fails behind a proxy, use the direct `endorctl` binary
  fallback.
- If Enterprise tools return authorization errors, verify the namespace,
  authentication mode, SSO tenant when applicable, and user permissions.
- If `security_review` is unavailable, confirm Enterprise Edition is enabled and
  AI security code review is enabled for the namespace.
