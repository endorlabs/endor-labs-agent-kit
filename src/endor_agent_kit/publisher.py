"""Publish compiled agent artifacts into a customer-facing catalog."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from endor_agent_kit.compilers import (
    compile_claude_code,
    compile_claude_managed_agents,
    compile_github_copilot_plugin,
    compile_raw,
)
from endor_agent_kit.compilers.claude_code import EDITIONS, _allows_read_only_endorctl
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.github_copilot_plugin import TARGET as GITHUB_COPILOT_PLUGIN_HOST
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host, load_recipe
from endor_agent_kit.validator import validate_recipe_file

MANIFEST_PATH = "manifest.json"
CLAUDE_CODE_HOST = "claude-code"
GENERATOR_NAME = "endor-agent-kit"
GITHUB_KEYLESS_AUTH_DOC = "github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md"


def publish_recipe(recipe_path: str | Path, dest: str | Path) -> list[Path]:
    """Publish one recipe's customer-facing artifacts into ``dest``."""

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    destination = Path(dest)
    destination.mkdir(parents=True, exist_ok=True)

    if CLAUDE_CODE_HOST in recipe.compatible_hosts or CLAUDE_MANAGED_AGENTS_HOST in recipe.compatible_hosts:
        compile_raw(recipe_file)
    written: list[Path] = []
    manifest: Path | None = None

    if CLAUDE_CODE_HOST in recipe.compatible_hosts:
        compile_claude_code(recipe_file)
        host_written, edition_records = _publish_claude_code(recipe_file, recipe, destination)
        written.extend(host_written)
        manifest = _write_manifest(destination, recipe, CLAUDE_CODE_HOST, edition_records)

    if CLAUDE_MANAGED_AGENTS_HOST in recipe.compatible_hosts:
        compile_claude_managed_agents(recipe_file)
        host_written, edition_records = _publish_claude_managed_agents(recipe_file, recipe, destination)
        written.extend(host_written)
        manifest = _write_manifest(destination, recipe, CLAUDE_MANAGED_AGENTS_HOST, edition_records)

    if GITHUB_COPILOT_PLUGIN_HOST in recipe.compatible_hosts:
        compile_github_copilot_plugin(recipe_file)
        host_written, edition_records = _publish_github_copilot_plugin(recipe_file, recipe, destination)
        written.extend(host_written)
        written.append(_write_github_keyless_auth_doc(destination))
        manifest = _write_manifest(destination, recipe, GITHUB_COPILOT_PLUGIN_HOST, edition_records)

    if manifest is not None:
        written.append(manifest)
    root_readme = _write_root_readme(destination)
    written.append(root_readme)
    return written


def publish_recipes(recipe_paths: list[str | Path], dest: str | Path, *, prune: bool = False) -> list[Path]:
    """Publish recipes, optionally removing previously published stale agents."""

    destination = Path(dest)
    recipe_files = [Path(recipe_path) for recipe_path in recipe_paths]
    active_host_agents: set[tuple[str, str]] = set()
    for recipe_file in recipe_files:
        errors = validate_recipe_file(recipe_file)
        if errors:
            raise ValueError("\n".join(errors))
        recipe = load_recipe(recipe_file)
        for host in recipe.compatible_hosts:
            active_host_agents.add((host, recipe.id))

    written: list[Path] = []
    for recipe_file in recipe_files:
        written.extend(publish_recipe(recipe_file, destination))

    if prune:
        manifest = _prune_stale_agents(destination, active_host_agents)
        if manifest is not None:
            written.append(manifest)
            written.append(_write_root_readme(destination))

    return written


def _publish_claude_code(
    recipe_file: Path,
    recipe: EndorAgentRecipe,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    agent_root = destination / CLAUDE_CODE_HOST / recipe.id
    if agent_root.exists():
        shutil.rmtree(agent_root)

    written: list[Path] = []
    edition_records: list[dict[str, Any]] = []
    for edition in editions_for_host(recipe, CLAUDE_CODE_HOST, EDITIONS):
        edition_dir = agent_root / edition
        edition_dir.mkdir(parents=True, exist_ok=True)
        artifact = edition_dir / f"{recipe.id}.md"
        source_artifact = recipe_file.parent / "dist" / CLAUDE_CODE_HOST / edition / f"{recipe.id}.md"
        shutil.copyfile(source_artifact, artifact)
        written.append(artifact)

        readme = edition_dir / "README.md"
        readme.write_text(_claude_code_edition_readme(recipe, edition), encoding="utf-8")
        written.append(readme)

        if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
            setup = edition_dir / "endorctl-setup.md"
            shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
            written.append(setup)

        edition_records.append(_edition_record(destination, recipe, edition, edition_dir))
    return written, edition_records


def _publish_claude_managed_agents(
    recipe_file: Path,
    recipe: EndorAgentRecipe,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    agent_root = destination / CLAUDE_MANAGED_AGENTS_HOST / recipe.id
    if agent_root.exists():
        shutil.rmtree(agent_root)

    written: list[Path] = []
    edition_records: list[dict[str, Any]] = []
    for edition in editions_for_host(recipe, CLAUDE_MANAGED_AGENTS_HOST, EDITIONS):
        edition_dir = agent_root / edition
        edition_dir.mkdir(parents=True, exist_ok=True)
        source_dir = recipe_file.parent / "dist" / CLAUDE_MANAGED_AGENTS_HOST / edition

        for filename in ("agent.yaml", "environment.yaml", "session-template.yaml"):
            artifact = edition_dir / filename
            shutil.copyfile(source_dir / filename, artifact)
            written.append(artifact)

        readme = edition_dir / "README.md"
        readme.write_text(_managed_agents_edition_readme(recipe, edition), encoding="utf-8")
        written.append(readme)

        if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
            setup = edition_dir / "endorctl-setup.md"
            shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
            written.append(setup)

        edition_records.append(_edition_record(destination, recipe, edition, edition_dir))
    return written, edition_records


def _publish_github_copilot_plugin(
    recipe_file: Path,
    recipe: EndorAgentRecipe,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    agent_root = destination / GITHUB_COPILOT_PLUGIN_HOST / recipe.id
    if agent_root.exists():
        shutil.rmtree(agent_root)

    written: list[Path] = []
    edition_records: list[dict[str, Any]] = []
    for edition in editions_for_host(recipe, GITHUB_COPILOT_PLUGIN_HOST, EDITIONS):
        edition_dir = agent_root / edition
        source_dir = recipe_file.parent / "dist" / GITHUB_COPILOT_PLUGIN_HOST / edition
        shutil.copytree(source_dir, edition_dir)
        files = sorted(path for path in edition_dir.rglob("*") if path.is_file())
        written.extend(files)
        edition_records.append(_edition_record(destination, recipe, edition, edition_dir))
    return written, edition_records


def _edition_record(destination: Path, recipe: EndorAgentRecipe, edition: str, edition_dir: Path) -> dict[str, Any]:
    files = sorted(path for path in edition_dir.rglob("*") if path.is_file())
    return {
        "id": edition,
        "name": _edition_name(edition),
        "artifacts": [_artifact_record(destination, path) for path in files],
        "requires_endorctl": recipe.requires_endorctl if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe) else "",
    }


def _artifact_record(destination: Path, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(destination).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _write_manifest(
    destination: Path,
    recipe: EndorAgentRecipe,
    host: str,
    edition_records: list[dict[str, Any]],
) -> Path:
    path = destination / MANIFEST_PATH
    agents = _existing_agents(path)
    agents = [
        agent
        for agent in agents
        if not (agent.get("id") == recipe.id and agent.get("host") == host)
    ]
    agents.append({
        "id": recipe.id,
        "name": recipe.name,
        "version": recipe.version,
        "host": host,
        "source": {
            "recipe_schema_version": recipe.recipe_schema_version,
            "builder_recipe": f"agents/{recipe.id}/recipe.yaml",
        },
        "editions": edition_records,
    })
    agents.sort(key=lambda agent: (str(agent.get("host", "")), str(agent.get("id", ""))))
    payload = {
        "schema_version": 1,
        "generated_by": GENERATOR_NAME,
        "agents": agents,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _existing_agents(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST_PATH}: expected a JSON object")
    agents = data.get("agents", [])
    if not isinstance(agents, list) or not all(isinstance(agent, dict) for agent in agents):
        raise ValueError(f"{MANIFEST_PATH}: expected agents to be a list of objects")
    return agents


def _prune_stale_agents(destination: Path, active_host_agents: set[tuple[str, str]]) -> Path | None:
    path = destination / MANIFEST_PATH
    if not path.exists():
        return None

    agents = _existing_agents(path)
    kept_agents = [
        agent
        for agent in agents
        if (str(agent.get("host", "")), str(agent.get("id", ""))) in active_host_agents
    ]
    stale_agents = [
        agent
        for agent in agents
        if (str(agent.get("host", "")), str(agent.get("id", ""))) not in active_host_agents
    ]
    if not stale_agents:
        return None

    for agent in stale_agents:
        host = str(agent.get("host", ""))
        agent_id = str(agent.get("id", ""))
        if host not in {CLAUDE_CODE_HOST, CLAUDE_MANAGED_AGENTS_HOST, GITHUB_COPILOT_PLUGIN_HOST} or not agent_id:
            continue
        shutil.rmtree(destination / host / agent_id, ignore_errors=True)

    kept_agents.sort(key=lambda agent: (str(agent.get("host", "")), str(agent.get("id", ""))))
    payload = {
        "schema_version": 1,
        "generated_by": GENERATOR_NAME,
        "agents": kept_agents,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_github_keyless_auth_doc(destination: Path) -> Path:
    path = destination / GITHUB_KEYLESS_AUTH_DOC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_github_keyless_auth_doc(), encoding="utf-8")
    return path


def _github_keyless_auth_doc() -> str:
    return "\n".join([
        "# Endor GitHub Keyless Auth For Copilot Agents",
        "",
        "GitHub Copilot cloud agent and AgentHQ run in a GitHub Actions-backed",
        "environment. Endor Labs can authenticate that workload with GitHub Actions OIDC",
        "when `endorctl` is started with GitHub action token support enabled.",
        "",
        "## Endor Labs Setup",
        "",
        "In Endor Labs, create an auth policy:",
        "",
        "- Identity provider: `GitHub Action OIDC`",
        "- Permission: the least-privileged role that can read the tenant data needed by",
        "  the agent; `Code Scanner` is the baseline role Endor documents for GitHub",
        "  Actions keyless authentication",
        "- Claim key: `user`",
        "- Claim value: the GitHub organization or owner that contains the target",
        "  repository",
        "",
        "## Target Repository Setup",
        "",
        "In the GitHub repository where Copilot cloud agent will run, create the",
        "`copilot` environment and add:",
        "",
        "- Environment variable: `COPILOT_MCP_ENDOR_NAMESPACE`",
        "- Optional environment variable: `COPILOT_MCP_ENDOR_API`",
        "",
        "Then add `.github/workflows/copilot-setup-steps.yml` to the target repository:",
        "",
        "```yaml",
        "name: \"Copilot Setup Steps\"",
        "",
        "on:",
        "  workflow_dispatch:",
        "  push:",
        "    paths:",
        "      - .github/workflows/copilot-setup-steps.yml",
        "  pull_request:",
        "    paths:",
        "      - .github/workflows/copilot-setup-steps.yml",
        "",
        "jobs:",
        "  copilot-setup-steps:",
        "    runs-on: ubuntu-latest",
        "    permissions:",
        "      id-token: write",
        "      contents: read",
        "    environment: copilot",
        "    steps:",
        "      - name: Configure Endor keyless auth",
        "        run: |",
        "          echo \"ENDOR_GITHUB_ACTION_TOKEN_ENABLE=true\" >> \"$GITHUB_ENV\"",
        "          echo \"ENDOR_NAMESPACE=${{ vars.COPILOT_MCP_ENDOR_NAMESPACE }}\" >> \"$GITHUB_ENV\"",
        "          echo \"ENDOR_API=${{ vars.COPILOT_MCP_ENDOR_API || 'https://api.endorlabs.com' }}\" >> \"$GITHUB_ENV\"",
        "```",
        "",
        "## Plugin MCP Configuration",
        "",
        "Enterprise GitHub Copilot plugin agents in this kit pass the same values into",
        "their local Endor MCP server:",
        "",
        "```yaml",
        "env:",
        "  ENDOR_GITHUB_ACTION_TOKEN_ENABLE: \"true\"",
        "  ENDOR_NAMESPACE: $COPILOT_MCP_ENDOR_NAMESPACE",
        "  ENDOR_API: ${COPILOT_MCP_ENDOR_API:-https://api.endorlabs.com}",
        "```",
        "",
        "This path intentionally uses Endor's GitHub Actions OIDC support rather than",
        "long-lived Endor API keys. It does not add an AgentHQ MCP `oidc` block, because",
        "`endorctl` performs the GitHub Actions OIDC exchange with Endor directly when",
        "`ENDOR_GITHUB_ACTION_TOKEN_ENABLE=true`.",
        "",
        "## Verification",
        "",
        "Start a Copilot cloud agent session and expand the setup logs:",
        "",
        "1. `Copilot Setup Steps` should run before MCP startup.",
        "2. The `endor-cli-tools` MCP server should start.",
        "3. Tenant lookups should succeed without Endor API key secrets.",
        "",
        "If Endor reports an auth failure, confirm the target repository owner matches",
        "the Endor auth policy claim and that the setup job has `id-token: write`.",
        "",
    ])


def _write_root_readme(destination: Path) -> Path:
    manifest = json.loads((destination / MANIFEST_PATH).read_text(encoding="utf-8"))
    agents = manifest.get("agents", [])
    path = destination / "README.md"
    path.write_text(_root_readme(agents), encoding="utf-8")
    return path


def _root_readme(agents: list[dict[str, Any]]) -> str:
    catalog = _agent_catalog(agents)
    agent_rows = []
    for item in catalog:
        agent_id = str(item["id"])
        claude_code_path = f"`{CLAUDE_CODE_HOST}/{agent_id}/`" if CLAUDE_CODE_HOST in item["hosts"] else "-"
        managed_path = (
            f"`{CLAUDE_MANAGED_AGENTS_HOST}/{agent_id}/`"
            if CLAUDE_MANAGED_AGENTS_HOST in item["hosts"]
            else "-"
        )
        github_copilot_path = (
            f"`{GITHUB_COPILOT_PLUGIN_HOST}/{agent_id}/`"
            if GITHUB_COPILOT_PLUGIN_HOST in item["hosts"]
            else "-"
        )
        agent_rows.append(
            f"| {item['name']} | {_agent_summary(agent_id)} | {claude_code_path} | {managed_path} | {github_copilot_path} |"
        )

    layout_agents = _repository_layout(agents)

    examples = []
    for item in catalog:
        agent_id = str(item["id"])
        examples.extend([
            f"{item['name']}:",
            "",
            "```text",
            _agent_example(agent_id),
            "```",
            "",
        ])

    return "\n".join([
        "# Endor Labs Agent Kit",
        "",
        "Ready-to-use Endor Labs agents for AI coding assistants, plus the",
        "recipe-first builder used to maintain and publish them.",
        "",
        "Use this repository in two ways:",
        "",
        "- **Install agents** from the generated catalog directories.",
        "- **Contribute agents** by editing source recipes and regenerating the catalog.",
        "",
        "## Table Of Contents",
        "",
        "- [Agent Catalog](#agent-catalog)",
        "- [Supported Hosts](#supported-hosts)",
        "- [Editions](#editions)",
        "- [Install An Agent](#install-an-agent)",
        "- [Configure Endor Access](#configure-endor-access)",
        "- [Example Prompts](#example-prompts)",
        "- [Output Contract](#output-contract)",
        "- [Safety Model](#safety-model)",
        "- [Contribute An Agent](#contribute-an-agent)",
        "- [Recipe Reference](#recipe-reference)",
        "- [Repository Reference](#repository-reference)",
        "- [Release And License](#release-and-license)",
        "",
        "## Agent Catalog",
        "",
        "Generated artifacts are checked in so users can copy or install agents without",
        "running the builder. Source recipes live under `agents/` and are the",
        "maintainer-facing source of truth.",
        "",
        "| Agent | Use it when you want to... | Claude Code | Claude Managed Agents | GitHub Copilot / AgentHQ plugin |",
        "| --- | --- | --- | --- | --- |",
        *agent_rows,
        "",
        "## Supported Hosts",
        "",
        "| Host | Generated path | Typical install target |",
        "| --- | --- | --- |",
        "| Claude Code | `claude-code/<agent>/<edition>/` | `.claude/agents/` in the target repository |",
        "| Claude Managed Agents | `claude-managed-agents/<agent>/<edition>/` | Anthropic Console or `ant` CLI agent and environment creation |",
        "| GitHub Copilot / AgentHQ plugin | `github-copilot-plugin/<agent>/<edition>/` | Copilot plugin package or AgentHQ app repository contents |",
        "",
        "## Editions",
        "",
        "Each agent is published in one or more editions. If an edition does not apply",
        "to a host, the catalog omits that host/edition directory.",
        "",
        "| Edition | Best for | Signals | Shell/execute access |",
        "| --- | --- | --- | --- |",
        "| Developer Edition | Fast, low-friction checks | Endor Model Context Protocol (MCP) tools | Not allowed |",
        "| Enterprise Edition | Richer Endor context when the agent supports it | Endor MCP tools, plus documented read-only `endorctl api` lookups for agents that need them | Agent-specific; always read-only |",
        "",
        "Use **Developer Edition** when you want the safest default with no Bash or",
        "execute access.",
        "",
        "Use **Enterprise Edition** when you have authenticated Endor setup and want",
        "the highest-fidelity signals available for that agent. Some Enterprise",
        "Edition agents are still MCP-only; their generated host configuration leaves",
        "shell or `execute` access disabled when no read-only `endorctl api` lookups",
        "are required.",
        "",
        "## Install An Agent",
        "",
        "Pick an agent from the catalog, then choose the host and edition directory",
        "that matches your environment.",
        "",
        "### Claude Code",
        "",
        "Copy the generated subagent into your target repository and restart Claude",
        "Code if needed.",
        "",
        "```bash",
        "mkdir -p .claude/agents",
        "cp /path/to/endor-labs-agent-kit/claude-code/dependency-decision-helper/developer-edition/dependency-decision-helper.md \\",
        "  .claude/agents/dependency-decision-helper.md",
        "```",
        "",
        "Then invoke it from Claude Code:",
        "",
        "```text",
        "@agent-dependency-decision-helper assess npm lodash version 4.17.20",
        "```",
        "",
        "### Claude Managed Agents",
        "",
        "Update the MCP server URL and vault references in the generated YAML",
        "templates, then create the agent and environment with the Anthropic CLI or",
        "Console.",
        "",
        "```bash",
        "cd /path/to/endor-labs-agent-kit/claude-managed-agents/dependency-decision-helper/developer-edition",
        "ant beta:agents create < agent.yaml",
        "ant beta:environments create < environment.yaml",
        "```",
        "",
        "Use `session-template.yaml` as the starting point when creating sessions.",
        "",
        "### GitHub Copilot / AgentHQ",
        "",
        "Install the generated plugin package with GitHub Copilot CLI from the",
        "package directory.",
        "",
        "```bash",
        "cd /path/to/endor-labs-agent-kit/github-copilot-plugin/vulnerability-explainer/developer-edition",
        "copilot plugin install .",
        "```",
        "",
        "For AgentHQ, use the generated plugin package as the public plugin repository",
        "contents for the corresponding Agentic App and edition.",
        "",
        "## Configure Endor Access",
        "",
        "| Access path | Used by | Notes |",
        "| --- | --- | --- |",
        "| Endor MCP | Developer Edition and Enterprise Edition agents | Required for every published agent. Configure it through the target host's MCP mechanism. |",
        "| Read-only `endorctl api` | Enterprise Edition agents that need tenant or project data beyond public MCP tools | The generated prompts constrain commands to documented read-only lookups. Per-edition README files link to `endorctl-setup.md` when needed. |",
        "| GitHub Actions keyless auth | Enterprise GitHub Copilot / AgentHQ plugins that need tenant data | Configure the target repository using `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`. |",
        "",
        "## Example Prompts",
        "",
        *examples,
        "## Output Contract",
        "",
        "Agents return concise prose plus a JSON block. The exact schema depends on the",
        "agent. If a signal is unavailable because of setup, authentication, account",
        "tier, or tooling, agents record that in `data_gaps` instead of inventing",
        "evidence.",
        "",
        "## Safety Model",
        "",
        "The agents in this kit are read-only.",
        "",
        "They do not:",
        "",
        "- edit files",
        "- create pull requests",
        "- run scans",
        "- dismiss findings",
        "- create policies",
        "- mutate Endor Labs state",
        "",
        "When an agent permits Bash, its prompt limits Bash to documented read-only Endor",
        "lookup commands. Claude Code artifacts deny Bash when it is not needed.",
        "Claude Managed Agents artifacts omit the pre-built agent toolset unless an",
        "agent needs read-only Bash, and then enable only Bash with confirmation.",
        "GitHub Copilot plugins enable `execute` only for Enterprise Edition agents",
        "that require the documented read-only Endor lookups.",
        "",
        "## Contribute An Agent",
        "",
        "This repository is both the source of truth and the distribution catalog.",
        "Contributor workflow is recipe-first: edit source files under `agents/`, then",
        "regenerate customer-facing artifacts.",
        "",
        "### Development Setup",
        "",
        "```bash",
        "python3 -m venv .venv",
        ". .venv/bin/activate",
        "python -m pip install --upgrade pip",
        "python -m pip install -e \".[dev]\"",
        "```",
        "",
        "### Authoring Workflow",
        "",
        "1. Edit `agents/<agent>/recipe.yaml`.",
        "2. Edit `agents/<agent>/instructions.md`.",
        "3. Update `agents/<agent>/evals/cases.yaml`.",
        "4. Add or update tests under `tests/`.",
        "5. Validate and regenerate the catalog.",
        "",
        "```bash",
        "endor-agent-kit validate agents/<agent>/recipe.yaml",
        "endor-agent-kit publish agents/*/recipe.yaml --dest . --prune",
        "python -m pytest -q",
        "git diff --exit-code -- README.md manifest.json claude-code claude-managed-agents github-copilot-plugin",
        "```",
        "",
        "Pull requests should include both source changes and regenerated artifacts.",
        "CI runs the same validation and generated-artifact drift check.",
        "",
        "### CLI Reference",
        "",
        "| Command | Purpose |",
        "| --- | --- |",
        "| `endor-agent-kit validate agents/<agent>/recipe.yaml` | Validate one recipe. |",
        "| `endor-agent-kit compile agents/<agent>/recipe.yaml --target <host>` | Compile one recipe into its local `dist/` directory. |",
        "| `endor-agent-kit compile agents/<agent>/recipe.yaml --target <host> --edition <edition>` | Compile one edition for one host. |",
        "| `endor-agent-kit publish agents/*/recipe.yaml --dest . --prune` | Regenerate the checked-in catalog and remove stale generated agents. |",
        "",
        "Supported compile targets are `claude-code`, `claude-managed-agents`,",
        "`github-copilot-plugin`, and `raw`.",
        "",
        "## Recipe Reference",
        "",
        "Recipes are YAML files with schema version `1`. They describe the agent's",
        "prompt, Endor access paths, host capabilities, inputs, outputs, evals, and",
        "published host editions.",
        "",
        "| Field | Purpose |",
        "| --- | --- |",
        "| `id`, `name`, `version`, `description` | Public catalog identity and copy. |",
        "| `safety_class`, `mutations` | Safety contract. v1 launch recipes are read-only and must not declare mutations. |",
        "| `supported_transports` | Endor access paths such as `mcp` and `endorctl_api`. |",
        "| `host_capabilities_required` | Abstract host capabilities that compilers map to host-specific tools. |",
        "| `inputs`, `outputs` | User-facing IO contract and expected JSON output shape. |",
        "| `compatible_hosts` | Hosts that should receive generated artifacts. |",
        "| `host_editions` | Optional host-specific edition selection. Omit to publish all default editions for that host. |",
        "| `required_endor_mcp_tools`, `endorctl_api_invocations` | Endor tools and read-only API lookups the prompt may use. |",
        "| `instructions_path`, `evals` | Source prompt and eval case files relative to the recipe. |",
        "",
        "Generated artifacts must not be edited as the first step. Change the recipe",
        "or instructions source, publish the catalog, then review the generated diff.",
        "",
        "## Repository Reference",
        "",
        "### Layout",
        "",
        "```text",
        "agents/",
        "  <agent>/",
        "    recipe.yaml",
        "    instructions.md",
        "    evals/cases.yaml",
        "src/endor_agent_kit/",
        "tests/",
        *layout_agents,
        "manifest.json",
        "```",
        "",
        "### Manifest",
        "",
        "`manifest.json` lists published artifacts and their SHA-256 checksums. Each",
        "manifest entry also records `source.builder_recipe`, which points back to the",
        "recipe that generated the artifact set.",
        "",
        "### Generated Catalog",
        "",
        "The root catalog directories are intentionally checked in:",
        "",
        "- `claude-code/`",
        "- `claude-managed-agents/`",
        "- `github-copilot-plugin/`",
        "- `manifest.json`",
        "",
        "These paths are customer-facing and should stay stable.",
        "",
        "## Release And License",
        "",
        "Before publishing a public release, verify that generated artifacts are fresh",
        "and that Endor Labs has selected and added the final open-source license.",
        "",
        "License information will be added before public release.",
        "",
    ])


def _agent_catalog(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for agent in agents:
        agent_id = str(agent.get("id") or "")
        if not agent_id:
            continue
        entry = catalog.setdefault(
            agent_id,
            {
                "id": agent_id,
                "name": _agent_name(agent),
                "hosts": set(),
            },
        )
        entry["hosts"].add(str(agent.get("host") or ""))
        if not entry.get("name"):
            entry["name"] = _agent_name(agent)
    return sorted(catalog.values(), key=lambda item: str(item["name"]).lower())


def _repository_layout(agents: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for host in (CLAUDE_CODE_HOST, CLAUDE_MANAGED_AGENTS_HOST, GITHUB_COPILOT_PLUGIN_HOST):
        host_agents = [agent for agent in agents if agent.get("host") == host]
        if not host_agents:
            continue
        lines.append(f"{host}/")
        for agent in sorted(host_agents, key=lambda item: str(item.get("id", ""))):
            agent_id = str(agent["id"])
            lines.append(f"  {agent_id}/")
            for edition in agent.get("editions", []):
                edition_id = str(edition.get("id", ""))
                lines.append(f"    {edition_id}/")
                for artifact in sorted(edition.get("artifacts", []), key=lambda item: str(item.get("path", ""))):
                    lines.append(f"      {Path(str(artifact['path'])).name}")
    return lines


def _agent_name(agent: dict[str, Any]) -> str:
    return str(agent.get("name") or agent.get("id") or "Endor Labs Agent")


def _agent_summary(agent_id: str) -> str:
    summaries = {
        "dependency-decision-helper": "Decide whether to add, upgrade to, or keep a specific package version",
        "upgrade-impact-analysis": "Analyze AURI-style upgrade impact with VersionUpgrade, CIA, findings, and manifest context",
        "package-risk-summary": "Summarize the risk profile of a specific package version",
        "tenant-findings": "Summarize tenant findings for an imported project, including reachable findings",
        "vulnerability-explainer": "Understand a specific CVE, GHSA, or Endor vulnerability and what to do next",
    }
    return summaries.get(agent_id, "Use an Endor Labs workflow agent")


def _agent_example(agent_id: str) -> str:
    examples = {
        "dependency-decision-helper": "@agent-dependency-decision-helper assess npm lodash version 4.17.20",
        "upgrade-impact-analysis": "@agent-upgrade-impact-analysis show the safest upgrade path for project <project_uuid> package lodash",
        "package-risk-summary": "@agent-package-risk-summary summarize npm lodash version 4.17.20",
        "tenant-findings": "@agent-tenant-findings show reachable findings for project <project_uuid>",
        "vulnerability-explainer": "@agent-vulnerability-explainer explain CVE-2021-44228",
    }
    return examples.get(agent_id, f"@agent-{agent_id} help")


def _claude_code_edition_readme(recipe: EndorAgentRecipe, edition: str) -> str:
    name = _edition_name(edition)
    if edition == "developer-edition" or not _allows_read_only_endorctl(recipe):
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor MCP access through the subagent's bundled MCP server config.",
            "No shell access or authenticated endorctl setup is required for this edition.",
        ]
        notes = [
            "This edition uses Endor MCP tools only.",
            "It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.",
        ]
    else:
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor MCP access through the subagent's bundled MCP server config.",
            "Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        notes = [
            "This edition uses MCP first, then read-only endorctl api lookups for richer signals.",
            "Bash use is limited by prompt to the documented Endor lookup commands.",
        ]

    return "\n".join([
        f"# {recipe.name} {name}",
        "",
        recipe.description.strip(),
        "",
        "## Install",
        "",
        f"Copy `{recipe.id}.md` into your target repository's `.claude/agents/` directory,",
        "then restart Claude Code if needed.",
        "",
        "## Requirements",
        "",
        *[f"- {item}" for item in requirements],
        "",
        "## Example",
        "",
        "```text",
        _example_prompt(recipe, edition),
        "```",
        "",
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def _managed_agents_edition_readme(recipe: EndorAgentRecipe, edition: str) -> str:
    name = _edition_name(edition)
    if edition == "developer-edition" or not _allows_read_only_endorctl(recipe):
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "A remote Endor MCP server URL configured in agent.yaml.",
            "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            "No pre-built Bash or filesystem tools are enabled for this edition.",
        ]
        notes = [
            "This edition uses the Managed Agents MCP connector only.",
            "The generated `agent.yaml` intentionally uses a placeholder MCP URL that must be replaced.",
            "Unavailable MCP, vault, auth, or account-tier signals are reported in data_gaps.",
        ]
    else:
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "A remote Endor MCP server URL configured in agent.yaml.",
            "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            "An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        notes = [
            "This edition uses MCP first, then read-only endorctl api lookups for richer signals.",
            "The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.",
            "Bash use remains limited by prompt to the documented Endor lookup commands.",
        ]

    return "\n".join([
        f"# {recipe.name} {name}",
        "",
        recipe.description.strip(),
        "",
        "## Install",
        "",
        "Update placeholders in `agent.yaml`, `environment.yaml`, and",
        "`session-template.yaml`, then create the agent and environment in",
        "Claude Managed Agents.",
        "",
        "```bash",
        "ant beta:agents create < agent.yaml",
        "ant beta:environments create < environment.yaml",
        "```",
        "",
        "Use `session-template.yaml` as the starting point for session creation after",
        "you have the created agent ID, environment ID, and any required vault IDs.",
        "",
        "## Requirements",
        "",
        *[f"- {item}" for item in requirements],
        "",
        "## Example User Message",
        "",
        "```text",
        _managed_example_prompt(recipe, edition),
        "```",
        "",
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def _edition_name(edition: str) -> str:
    if edition == "developer-edition":
        return "Developer Edition"
    if edition == "enterprise-edition":
        return "Enterprise Edition"
    raise ValueError(f"Unknown edition {edition!r}")


def _example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    input_names = {field.name for field in recipe.inputs}
    if "vulnerability_id" in input_names:
        return f"@agent-{recipe.id} explain CVE-2021-44228"
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return f"@agent-{recipe.id} assess npm lodash from 4.17.20 to 4.17.21"
        return f"@agent-{recipe.id} show the safest upgrade path for project <project_uuid> package lodash, including CIA and manifest files"
    if recipe.id == "package-risk-summary":
        return f"@agent-{recipe.id} summarize npm lodash version 4.17.20"
    if recipe.id == "tenant-findings":
        return f"@agent-{recipe.id} show reachable findings for project <project_uuid>"
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return f"@agent-{recipe.id} assess npm lodash version 4.17.20"
    return f"@agent-{recipe.id} help"


def _managed_example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    input_names = {field.name for field in recipe.inputs}
    if "vulnerability_id" in input_names:
        return "Explain CVE-2021-44228."
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return "Assess upgrading npm lodash from 4.17.20 to 4.17.21."
        return "Show the safest upgrade path for project <project_uuid> package lodash, including CIA, findings fixed, manifest files, and breaking changes."
    if recipe.id == "package-risk-summary":
        return "Summarize npm lodash version 4.17.20."
    if recipe.id == "tenant-findings":
        return "Show reachable findings for project <project_uuid>."
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return "Assess npm lodash version 4.17.20."
    return "Help me use this Endor Labs agent."
