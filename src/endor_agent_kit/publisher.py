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
    compile_codex,
    compile_raw,
)
from endor_agent_kit.compilers.claude_code import EDITIONS, _allows_read_only_endorctl, _uses_mcp
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host, load_recipe
from endor_agent_kit.validator import validate_recipe_file

MANIFEST_PATH = "manifest.json"
CLAUDE_CODE_HOST = "claude-code"
GENERATOR_NAME = "endor-agent-kit"
PUBLISHED_HOSTS = (CLAUDE_CODE_HOST, CLAUDE_MANAGED_AGENTS_HOST, CODEX_HOST)


def publish_recipe(recipe_path: str | Path, dest: str | Path) -> list[Path]:
    """Publish one recipe's customer-facing artifacts into ``dest``."""

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    destination = Path(dest)
    destination.mkdir(parents=True, exist_ok=True)

    if (
        CLAUDE_CODE_HOST in recipe.compatible_hosts
        or CLAUDE_MANAGED_AGENTS_HOST in recipe.compatible_hosts
        or CODEX_HOST in recipe.compatible_hosts
    ):
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

    if CODEX_HOST in recipe.compatible_hosts:
        compile_codex(recipe_file)
        host_written, edition_records = _publish_codex(recipe_file, recipe, destination)
        written.extend(host_written)
        manifest = _write_manifest(destination, recipe, CODEX_HOST, edition_records)

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
    architecture_source = _architecture_source(recipe_file)
    has_architecture = architecture_source.is_file()
    editions = editions_for_host(recipe, CLAUDE_CODE_HOST, EDITIONS)
    flat_layout = len(editions) == 1
    for edition in editions:
        edition_dir = _published_edition_dir(agent_root, editions, edition)
        edition_dir.mkdir(parents=True, exist_ok=True)
        artifact = edition_dir / f"{recipe.id}.md"
        source_artifact = recipe_file.parent / "dist" / CLAUDE_CODE_HOST / edition / f"{recipe.id}.md"
        shutil.copyfile(source_artifact, artifact)
        written.append(artifact)

        readme = edition_dir / "README.md"
        readme.write_text(
            _claude_code_edition_readme(
                recipe,
                edition,
                has_architecture=has_architecture,
                show_edition_name=not flat_layout,
            ),
            encoding="utf-8",
        )
        written.append(readme)

        if has_architecture:
            architecture = edition_dir / "architecture.svg"
            shutil.copyfile(architecture_source, architecture)
            written.append(architecture)

        actions_source = _actions_source(recipe_file, recipe)
        if actions_source.is_file():
            actions = edition_dir / "actions.yaml"
            shutil.copyfile(actions_source, actions)
            written.append(actions)

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
    architecture_source = _architecture_source(recipe_file)
    has_architecture = architecture_source.is_file()
    editions = editions_for_host(recipe, CLAUDE_MANAGED_AGENTS_HOST, EDITIONS)
    flat_layout = len(editions) == 1
    for edition in editions:
        edition_dir = _published_edition_dir(agent_root, editions, edition)
        edition_dir.mkdir(parents=True, exist_ok=True)
        source_dir = recipe_file.parent / "dist" / CLAUDE_MANAGED_AGENTS_HOST / edition

        for filename in ("agent.yaml", "environment.yaml", "session-template.yaml"):
            artifact = edition_dir / filename
            shutil.copyfile(source_dir / filename, artifact)
            written.append(artifact)

        readme = edition_dir / "README.md"
        readme.write_text(
            _managed_agents_edition_readme(
                recipe,
                edition,
                has_architecture=has_architecture,
                show_edition_name=not flat_layout,
            ),
            encoding="utf-8",
        )
        written.append(readme)

        if has_architecture:
            architecture = edition_dir / "architecture.svg"
            shutil.copyfile(architecture_source, architecture)
            written.append(architecture)

        actions_source = _actions_source(recipe_file, recipe)
        if actions_source.is_file():
            actions = edition_dir / "actions.yaml"
            shutil.copyfile(actions_source, actions)
            written.append(actions)

        if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
            setup = edition_dir / "endorctl-setup.md"
            shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
            written.append(setup)

        edition_records.append(_edition_record(destination, recipe, edition, edition_dir))
    return written, edition_records


def _publish_codex(
    recipe_file: Path,
    recipe: EndorAgentRecipe,
    destination: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    agent_root = destination / CODEX_HOST / recipe.id
    if agent_root.exists():
        shutil.rmtree(agent_root)
    agent_root.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    source_dir = recipe_file.parent / "dist" / CODEX_HOST / recipe.id
    skill = agent_root / "SKILL.md"
    shutil.copyfile(source_dir / "SKILL.md", skill)
    written.append(skill)

    architecture_source = _architecture_source(recipe_file)
    has_architecture = architecture_source.is_file()

    readme = agent_root / "README.md"
    readme.write_text(_codex_readme(recipe, has_architecture=has_architecture), encoding="utf-8")
    written.append(readme)

    if has_architecture:
        architecture = agent_root / "architecture.svg"
        architecture.write_text(
            _codex_text(architecture_source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        written.append(architecture)

    actions_source = _actions_source(recipe_file, recipe)
    if actions_source.is_file():
        actions = agent_root / "actions.yaml"
        actions.write_text(
            _codex_text(actions_source.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        written.append(actions)

    if _allows_read_only_endorctl(recipe) or recipe.safety_class == "mutating":
        setup = agent_root / "endorctl-setup.md"
        shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
        written.append(setup)

    return written, [
        _artifact_bundle_record(
            destination,
            recipe,
            "codex-skill",
            "Codex Skill",
            agent_root,
            requires_endorctl=recipe.requires_endorctl
            if (_allows_read_only_endorctl(recipe) or recipe.safety_class == "mutating")
            else "",
        )
    ]


def _published_edition_dir(agent_root: Path, editions: tuple[str, ...], edition: str) -> Path:
    if len(editions) == 1:
        return agent_root
    return agent_root / edition


def _edition_record(destination: Path, recipe: EndorAgentRecipe, edition: str, edition_dir: Path) -> dict[str, Any]:
    return _artifact_bundle_record(
        destination,
        recipe,
        edition,
        _edition_name(edition),
        edition_dir,
        requires_endorctl=recipe.requires_endorctl
        if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe)
        else "",
    )


def _artifact_bundle_record(
    destination: Path,
    recipe: EndorAgentRecipe,
    bundle_id: str,
    bundle_name: str,
    bundle_dir: Path,
    *,
    requires_endorctl: str = "",
) -> dict[str, Any]:
    files = sorted(path for path in bundle_dir.rglob("*") if path.is_file())
    return {
        "id": bundle_id,
        "name": bundle_name,
        "path": bundle_dir.relative_to(destination).as_posix(),
        "artifacts": [_artifact_record(destination, path) for path in files],
        "requires_endorctl": requires_endorctl,
    }


def _architecture_source(recipe_file: Path) -> Path:
    return recipe_file.parent / "architecture.svg"


def _actions_source(recipe_file: Path, recipe: EndorAgentRecipe) -> Path:
    if not recipe.action_contracts_path:
        return recipe_file.parent / "__no_actions_yaml__"
    return recipe_file.parent / recipe.action_contracts_path


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
            "builder_recipe": f"source/agents/{recipe.id}/recipe.yaml",
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
        if host not in set(PUBLISHED_HOSTS) or not agent_id:
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
        codex_path = f"`{CODEX_HOST}/{agent_id}/`" if CODEX_HOST in item["hosts"] else "-"
        agent_rows.append(
            f"| {item['name']} | {_agent_summary(agent_id)} | {claude_code_path} | {managed_path} | {codex_path} |"
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
        if agent_id == "sca-remediation":
            examples.extend([
                "Other non-breaking low-risk UIA-backed PRs:",
                "",
                "```text",
                "@agent-sca-remediation show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and the risky solver. Do not edit files, create branches, push, or open a PR/MR.",
                "```",
                "",
                "SCA remediation PR plan:",
                "",
                "```text",
                "@agent-sca-remediation prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
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
        "- [Which Directory Do I Use?](#which-directory-do-i-use)",
        "- [Supported Hosts](#supported-hosts)",
        "- [MCP Usage](#mcp-usage)",
        "- [Plugin Packaging Route](#plugin-packaging-route)",
        "- [Editions](#editions)",
        "- [Install An Agent](#install-an-agent)",
        "- [Configure Endor Access](#configure-endor-access)",
        "- [Example Prompts](#example-prompts)",
        "- [Output Contract](#output-contract)",
        "- [Safety Model](#safety-model)",
        "- [Contribute An Agent](#contribute-an-agent)",
        "- [Create Agents With The Skill](#create-agents-with-the-skill)",
        "- [Recipe Reference](#recipe-reference)",
        "- [Repository Reference](#repository-reference)",
        "- [Release And License](#release-and-license)",
        "",
        "## Agent Catalog",
        "",
        "Generated artifacts are checked in so users can copy or install agents without",
        "running the builder. Maintainer source recipes live under `source/agents/` and are the",
        "maintainer-facing source of truth.",
        "",
        "If you are installing an agent, start with the generated host directories below.",
        "You only need `source/agents/` when you are changing or contributing an agent.",
        "",
        "| Agent | Use it when you want to... | Claude Code | Claude Managed Agents | Codex |",
        "| --- | --- | --- | --- | --- |",
        *agent_rows,
        "",
        "## Which Directory Do I Use?",
        "",
        "| Goal | Start Here | You Do Not Need |",
        "| --- | --- | --- |",
        "| Install a Claude Code agent | `claude-code/<agent>/README.md` | `source/`, `src/`, `tests/` |",
        "| Install a Claude Managed Agent | `claude-managed-agents/<agent>/README.md` | `source/`, `src/`, `tests/` |",
        "| Install a Codex skill | `codex/<agent>/README.md` | `source/`, `src/`, `tests/` |",
        "| Modify or contribute an agent | `source/agents/<agent>/recipe.yaml` and `instructions.md` | Generated catalog files as the first edit |",
        "| Work on the kit builder itself | `src/endor_agent_kit/` and `tests/` | Host install directories unless compiler output changes |",
        "",
        "The `source/agents/` tree is for maintainers and contributors. It is not",
        "copied into Claude Code or Managed Agents. Installable artifacts",
        "are the generated host directories listed in the catalog.",
        "",
        "## Supported Hosts",
        "",
        "| Host | Generated path | Typical install target |",
        "| --- | --- | --- |",
        "| Claude Code | `claude-code/<agent>/` | `.claude/agents/` in the target repository |",
        "| Claude Managed Agents | `claude-managed-agents/<agent>/` | Anthropic Console or `ant` CLI agent and environment creation |",
        "| Codex | `codex/<agent>/` | `$CODEX_HOME/skills/<agent>/` or `~/.codex/skills/<agent>/` |",
        "",
        "## MCP Usage",
        "",
        "MCP is not used by the mutating remediation workflows. AI SAST Triage, SCA",
        "Remediation, Remediation Planner, Upgrade Impact Analysis, and the Codex",
        "skills use documented Endor API or `endorctl api` paths instead.",
        "",
        "MCP remains in the catalog only where the current public recipe still depends",
        "on Endor package/vulnerability lookup tools that do not yet have an",
        "`endorctl api` contract in this kit:",
        "",
        "| Agent | MCP use | Non-MCP path in same artifact |",
        "| --- | --- | --- |",
        "| Dependency Decision Helper | Package risk, vulnerability list, and vulnerability enrichment. | `endorctl api` for package scores, license, and similar-package signals. |",
        "| Endor Labs Package Risk Summary | Package risk, vulnerability list, and vulnerability enrichment. | `endorctl api` for package scores, license, and similar-package signals. |",
        "| Endor Labs Repository Dependency Reviewer | Per-dependency risk and vulnerability checks after local read-only manifest inspection. | None in v0. |",
        "| Endor Labs Vulnerability Explainer | Vulnerability detail lookup. | None in v0. |",
        "",
        "If MCP is unavailable, those agents must record the missing signal in",
        "`data_gaps` rather than blocking install or fabricating evidence.",
        "",
        "## Plugin Packaging Route",
        "",
        "Codex support currently publishes generated skills under `codex/<agent>/`.",
        "A future plugin package can wrap those skills for easier installation, but",
        "the plugin route should preserve the same recipe source, generated skill",
        "text, action metadata, and approval gates. See",
        "`docs/plugin-packaging-design.md` for the current blast-radius notes before",
        "adding plugin publishing.",
        "",
        "## Editions",
        "",
        "Most users should not need to think about editions. The current catalog",
        "publishes one customer-facing artifact per agent and host, directly under",
        "`claude-code/<agent>/`, `claude-managed-agents/<agent>/`, or",
        "`codex/<agent>/`.",
        "",
        "The builder still understands internal `developer-edition` and",
        "`enterprise-edition` recipe sections for compatibility and for future",
        "agents that genuinely need multiple artifacts. When a recipe selects one",
        "artifact, the published directory is flat and the generated README omits the",
        "edition label.",
        "",
        "Shell access is still controlled by each recipe's host capability contract.",
        "Read-only agents that do not need `endorctl api` deny Bash. Read-only agents",
        "that need `endorctl api` allow Bash only for documented read-only Endor",
        "lookup commands. Mutating agents keep file edits, branch pushes, PR/MR",
        "creation, comments, approval verification, and Endor policy writes behind",
        "separate approval gates.",
        "",
        "## Install An Agent",
        "",
        "Pick an agent from the catalog, then open that host directory's README. If",
        "the agent has edition subdirectories, choose the one that matches your",
        "environment; otherwise use the agent directory directly.",
        "",
        "### Ask An LLM To Install It",
        "",
        "If you are using an assistant that can edit files or run commands in your",
        "target repository, copy and paste this prompt:",
        "",
        "```text",
        "Install this Endor Labs Agent Kit agent in the current repository.",
        "",
        "Agent Kit root: /path/to/endor-labs-agent-kit",
        "Host: claude-code",
        "Agent directory: claude-code/ai-sast-triage",
        "",
        "Please:",
        "1. Read the install README at <Agent Kit root>/<Agent directory>/README.md.",
        "2. Install the generated agent artifact from that directory into this repository.",
        "3. Preserve the generated agent prompt exactly; do not rewrite or summarize it.",
        "4. Tell me any Endor MCP if declared, endorctl, repository, or credential setup still required.",
        "5. Show me the command or prompt I should use to invoke the agent.",
        "```",
        "",
        "Replace `Agent directory` with the directory you selected from the catalog.",
        "",
        "### Claude Code",
        "",
        "Copy the generated subagent into your target repository and restart Claude",
        "Code if needed.",
        "",
        "```bash",
        "mkdir -p .claude/agents",
        "cp /path/to/endor-labs-agent-kit/claude-code/ai-sast-triage/ai-sast-triage.md \\",
        "  .claude/agents/ai-sast-triage.md",
        "```",
        "",
        "Then invoke it from Claude Code:",
        "",
        "```text",
        "@agent-ai-sast-triage triage AI SAST findings for this repository",
        "```",
        "",
        "### Claude Managed Agents",
        "",
        "Create the agent and environment with the Anthropic CLI or Console. If the",
        "selected agent declares MCP in its generated `README.md`, update the MCP",
        "server URL and vault references in the generated YAML first.",
        "",
        "```bash",
        "cd /path/to/endor-labs-agent-kit/claude-managed-agents/dependency-decision-helper",
        "ant beta:agents create < agent.yaml",
        "ant beta:environments create < environment.yaml",
        "```",
        "",
        "Use `session-template.yaml` as the starting point when creating sessions.",
        "",
        "### Codex",
        "",
        "Copy the generated skill directory into your Codex skills directory, then",
        "start a new Codex session so the skill loader can see it.",
        "",
        "```bash",
        "mkdir -p \"${CODEX_HOME:-$HOME/.codex}/skills\"",
        "cp -R /path/to/endor-labs-agent-kit/codex/ai-sast-triage \\",
        "  \"${CODEX_HOME:-$HOME/.codex}/skills/ai-sast-triage\"",
        "cp -R /path/to/endor-labs-agent-kit/codex/sca-remediation \\",
        "  \"${CODEX_HOME:-$HOME/.codex}/skills/sca-remediation\"",
        "```",
        "",
        "Then invoke it from Codex:",
        "",
        "```text",
        "Use the ai-sast-triage skill to triage AI SAST findings for this repository.",
        "Use the sca-remediation skill to check this repository for P0 SCA findings I can start remediating.",
        "```",
        "",
        "## Configure Endor Access",
        "",
        "| Access path | Used by | Notes |",
        "| --- | --- | --- |",
        "| Endor MCP | Agents whose generated artifact declares an MCP server | Configure it through the target host's MCP mechanism only when the selected agent requires it. |",
        "| `endorctl api` or direct Endor API | Agents that need tenant, project, finding, or policy data without MCP | The generated prompts constrain commands to documented lookups and writes. Agent or edition README files link to `endorctl-setup.md` when needed. |",
        "| Git and source-provider credentials | Mutating Claude Code agents such as AI SAST Triage and SCA Remediation | Required when the agent is expected to apply patches, open change requests, read PR/MR approval evidence, or post PR/MR comments. |",
        "| Codex terminal and file-editing tools | Codex skills for mutating agents such as AI SAST Triage and SCA Remediation | The skill keeps file edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes behind separate approval gates. |",
        "| Endor policy-write access | AI SAST Triage standalone exceptions | Required only when a verified AppSec PR/MR approval should create a scoped Endor exception policy. The agent must show the policy spec and ask for confirmation before writing. |",
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
        "SCA remediation outputs can be checked mechanically before a workflow advances:",
        "",
        "```bash",
        "endor-agent-kit validate-sca-output sca-output.json --gate selection-plan",
        "endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md",
        "endor-agent-kit lint-sca-pr-body pr-body.md",
        "endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo",
        "endor-agent-kit check-install --host codex --agent sca-remediation --codex-home ~/.codex",
        "endor-agent-kit validate-ai-sast-output ai-sast-output.json --gate remediation",
        "endor-agent-kit render-ai-sast-pr-body ai-sast-output.json > pr-body.md",
        "endor-agent-kit lint-ai-sast-pr-body pr-body.md",
        "endor-agent-kit render-ai-sast-approval-comment ai-sast-output.json > approval-comment.md",
        "endor-agent-kit lint-ai-sast-approval-comment approval-comment.md",
        "endor-agent-kit render-ai-sast-exception-policy-comment ai-sast-output.json > policy-comment.md",
        "endor-agent-kit lint-ai-sast-exception-policy-comment policy-comment.md",
        "```",
        "",
        "`validate-sca-output` rejects Selection / Plan responses that omit",
        "`risk_decision.status`, use nonstandard branch names, or try to advance a",
        "CIA-indeterminate upgrade without source-usage evidence and validation",
        "requirements. `render-sca-pr-body` turns normalized advisory data into the",
        "AURI-style PR/MR body, including the folded advisory list, CVE-visible links",
        "to GHSA URLs, and severity emoji suffixes.",
        "`check-install` catches copied Claude Code agents that are stale versus the",
        "checked-in Agent Kit catalog.",
        "",
        "AI SAST triage outputs can be checked before remediation, PR/MR, or",
        "exception-policy gates advance. `validate-ai-sast-output` requires",
        "project and namespace provenance, finding/source-location provenance,",
        "approval evidence before exception policies, and a rendered PR/MR body",
        "when a remediation change request is part of the plan. For exception",
        "policies it also checks accepted-risk expiration, approval reason",
        "matching, approved finding scope, project selector scope, policy names,",
        "idempotency checks, and human-readable decision comments. The AI SAST",
        "PR/MR renderer follows the AURI AI SAST remediation structure with",
        "`auri:ai-sast-context` metadata, severity indicator emojis, sanitized",
        "AURI evidence, a standalone exception-request prompt block, folded finding details,",
        "and standalone Agent Kit policy-write gates that still require independent",
        "AppSec approval before any Endor policy write. Standalone Agent Kit is not",
        "a webhook listener: PR/MR comments are approval evidence, and a user or",
        "external automation must invoke the installed agent before any policy can",
        "be created or reused.",
        "",
        "For `sca-remediation`, keep the three remediation lanes distinct:",
        "",
        "- P0/exploited remediation candidates: rank reachable or exploited critical/high findings and require UIA evidence before naming a best fix.",
        "- Other non-breaking low-risk UIA-backed PRs: list only low-risk, CIA-clean recommendations with zero introduced findings and enough repo metadata to open a PR/MR.",
        "- Risky or indeterminate upgrades: use `risk_decision` from Endor evidence plus local source usage before applying or opening a change request.",
        "",
        "The low-risk lane reports `low_risk_recommendations`, `candidate_prs`,",
        "`ready_to_open`, `most_findings_in_one_pr`, and `p0_duplicates_hidden`.",
        "Validation commands must come from the repository's actual manifest and",
        "package-manager layout; the agent must not assume Java, Maven, npm, Python,",
        "Go, .NET, Ruby, Rust, or any other ecosystem from prior runs.",
        "",
        "## Safety Model",
        "",
        "Most agents in this kit are read-only. Recipes declare their safety class and",
        "host capabilities explicitly.",
        "",
        "Read-only agents do not:",
        "",
        "- edit files",
        "- create pull requests",
        "- run scans",
        "- dismiss findings",
        "- create policies",
        "- mutate Endor Labs state",
        "",
        "Mutating agents are published only when their recipe declares the required",
        "host capabilities. AI SAST Triage and SCA Remediation may fetch source",
        "context, write patch files, run git/source-provider commands, and open a",
        "change request when the user asks for that workflow and the target repository",
        "credentials are available.",
        "",
        "When a read-only agent permits Bash, its prompt limits Bash to documented",
        "read-only Endor lookup commands. Claude Code artifacts deny Bash when it is",
        "not needed.",
        "",
        "When a recipe declares `host_capabilities_required.read_files: true`,",
        "Claude Code artifacts allow only `Read`, `Glob`, `Grep`, and `LS` for",
        "read-only workspace inspection; file mutation, notebook, web, and todo tools",
        "remain denied.",
        "Claude Managed Agents artifacts omit the pre-built agent toolset unless an",
        "agent needs read-only Bash, and then enable only Bash with confirmation.",
        "",
        "## Contribute An Agent",
        "",
        "This repository is both the source of truth and the distribution catalog.",
        "Contributor workflow is recipe-first: edit source files under `source/agents/`, then",
        "regenerate customer-facing artifacts.",
        "",
        "### Create Agents With The Skill",
        "",
        "Use the Create Endor Labs Agent skill to make your own Endor Labs agent.",
        "The skill lives at `skills/create-endor-labs-agent/SKILL.md` and guides an",
        "assistant through agent design, recipe authoring, prompt sections, evals,",
        "architecture diagrams, tests, catalog regeneration, and validation.",
        "",
        "The skill supports two public input styles: a net-new agent brief or a",
        "generic sanitized agent blueprint. Private tools may generate a blueprint,",
        "but Agent Kit should only receive customer-safe recipe, action, instruction,",
        "eval, and architecture source files.",
        "",
        "For Claude Code, install it at either the repository or user level:",
        "",
        "```bash",
        "# Repository-level install",
        "mkdir -p .claude/skills",
        "cp -R skills/create-endor-labs-agent .claude/skills/",
        "",
        "# User-level install",
        "mkdir -p ~/.claude/skills",
        "cp -R skills/create-endor-labs-agent ~/.claude/skills/",
        "```",
        "",
        "Then ask your assistant:",
        "",
        "```text",
        "Use the create Endor Labs agent skill to make an agent that <does the workflow you want>.",
        "```",
        "",
        "You can also point any agent directly at",
        "`skills/create-endor-labs-agent/SKILL.md` if it does not support native",
        "skills.",
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
        "1. Edit `source/agents/<agent>/recipe.yaml`.",
        "2. Edit `source/agents/<agent>/instructions.md`.",
        "3. Update `source/agents/<agent>/evals/cases.yaml`.",
        "4. Add `source/agents/<agent>/architecture.svg` in the existing diagram format.",
        "5. Add or update tests under `tests/`.",
        "6. Validate and regenerate the catalog.",
        "",
        "```bash",
        "endor-agent-kit validate source/agents/<agent>/recipe.yaml",
        "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune",
        "python -m pytest -q",
        "git diff --exit-code -- README.md manifest.json claude-code claude-managed-agents",
        "```",
        "",
        "Pull requests should include both source changes and regenerated artifacts.",
        "CI runs the same validation and generated-artifact drift check.",
        "",
        "### CLI Reference",
        "",
        "| Command | Purpose |",
        "| --- | --- |",
        "| `endor-agent-kit validate source/agents/<agent>/recipe.yaml` | Validate one recipe. |",
        "| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host>` | Compile one recipe into its local `dist/` directory. |",
        "| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host> --edition <edition>` | Compile one edition for one host. |",
        "| `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune` | Regenerate the checked-in catalog and remove stale generated agents. |",
        "| `endor-agent-kit validate-sca-output sca-output.json --gate selection-plan` | Validate structured `sca-remediation` output before advancing a workflow gate. |",
        "| `endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md` | Render the AURI-style SCA remediation PR/MR body from normalized JSON. |",
        "| `endor-agent-kit lint-sca-pr-body pr-body.md` | Lint a rendered SCA remediation PR/MR body for required sections, advisory formatting, and severity suffixes. |",
        "| `endor-agent-kit validate-ai-sast-output ai-sast-output.json --gate remediation` | Validate structured `ai-sast-triage` output before remediation, PR/MR, or exception gates advance. |",
        "| `endor-agent-kit render-ai-sast-pr-body ai-sast-output.json > pr-body.md` | Render an AURI-style AI SAST remediation PR/MR body from normalized JSON. |",
        "| `endor-agent-kit lint-ai-sast-pr-body pr-body.md` | Lint an AURI-style AI SAST remediation PR/MR body for required sections, hidden context metadata, and severity indicators. |",
        "| `endor-agent-kit render-ai-sast-approval-comment ai-sast-output.json > approval-comment.md` | Render a standalone AppSec approval request comment. |",
        "| `endor-agent-kit lint-ai-sast-approval-comment approval-comment.md` | Lint the approval request comment and exact approval phrase. |",
        "| `endor-agent-kit render-ai-sast-exception-policy-comment ai-sast-output.json > policy-comment.md` | Render a human-readable Endor exception policy decision comment. |",
        "| `endor-agent-kit lint-ai-sast-exception-policy-comment policy-comment.md` | Lint the policy decision comment for policy name/UUID, project label, evidence, and raw selector leakage. |",
        "| `endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo` | Check whether a copied repo-level Claude Code agent matches the generated catalog artifact. |",
        "| `endor-agent-kit check-install --host codex --agent sca-remediation --codex-home ~/.codex` | Check whether an installed Codex skill matches the generated catalog artifact. |",
        "",
        "Supported compile targets are `claude-code`, `claude-managed-agents`,",
        "`codex`, and `raw`.",
        "",
        "## Recipe Reference",
        "",
        "Recipes are YAML files with schema version `1` or `2`. They describe the agent's",
        "prompt, Endor access paths, host capabilities, inputs, outputs, evals, and",
        "published host editions. Schema v2 recipes may also point to `actions.yaml`",
        "for semantic side-effect contracts such as opening change requests or",
        "requesting exception-policy approval.",
        "",
        "| Field | Purpose |",
        "| --- | --- |",
        "| `id`, `name`, `version`, `description` | Public catalog identity and copy. |",
        "| `safety_class`, `mutations` | Safety contract. Recipes may be `read_only`, `dry_run`, or explicitly `mutating` with matching host capabilities. |",
        "| `supported_transports` | Endor access paths such as `mcp` and `endorctl_api`. |",
        "| `host_capabilities_required` | Abstract host capabilities that compilers map to host-specific tools. |",
        "| `action_contracts_path` | Optional schema v2 path to `actions.yaml`, which declares semantic side effects and adapter requirements. |",
        "| `inputs`, `outputs` | User-facing IO contract and expected JSON output shape. |",
        "| `compatible_hosts` | Hosts that should receive generated artifacts. |",
        "| `host_editions` | Optional host-specific edition selection. Omit to publish all default editions for that host. |",
        "| `required_endor_mcp_tools`, `endorctl_api_invocations` | Endor tools and API lookup groups the prompt may use. |",
        "| `instructions_path`, `evals` | Source prompt and eval case files relative to the recipe. |",
        "| `architecture.svg` | Required source diagram copied into generated catalog artifacts when present. |",
        "",
        "Generated artifacts must not be edited as the first step. Change the recipe",
        "or instructions source, publish the catalog, then review the generated diff.",
        "",
        "## Repository Reference",
        "",
        "### Layout",
        "",
        "```text",
        "source/",
        "  agents/",
        "    <agent>/",
        "      recipe.yaml",
        "      actions.yaml",
        "      instructions.md",
        "      evals/cases.yaml",
        "skills/",
        "  create-endor-labs-agent/",
        "    SKILL.md",
        "docs/",
        "  plugin-packaging-design.md",
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
        "- `codex/`",
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
    for host in PUBLISHED_HOSTS:
        host_agents = [agent for agent in agents if agent.get("host") == host]
        if not host_agents:
            continue
        lines.append(f"{host}/")
        for agent in sorted(host_agents, key=lambda item: str(item.get("id", ""))):
            agent_id = str(agent["id"])
            lines.append(f"  {agent_id}/")
            for edition in agent.get("editions", []):
                edition_path = str(edition.get("path") or "")
                flat_layout = edition_path == f"{host}/{agent_id}"
                if not flat_layout:
                    edition_id = str(edition.get("id", ""))
                    lines.append(f"    {edition_id}/")
                for artifact in sorted(edition.get("artifacts", []), key=lambda item: str(item.get("path", ""))):
                    indent = "    " if flat_layout else "      "
                    lines.append(f"{indent}{Path(str(artifact['path'])).name}")
    return lines


def _agent_name(agent: dict[str, Any]) -> str:
    return str(agent.get("name") or agent.get("id") or "Endor Labs Agent")


def _agent_summary(agent_id: str) -> str:
    summaries = {
        "ai-sast-triage": "Triage Endor AI SAST findings, use exploit and remediation context, and open requested change requests",
        "dependency-decision-helper": "Decide whether to add, upgrade to, or keep a specific package version",
        "upgrade-impact-analysis": "Analyze Endor platform upgrade impact with VersionUpgrade, CIA, findings, and manifest context",
        "package-risk-summary": "Summarize the risk profile of a specific package version",
        "remediation-planner": "Preview safe dependency remediation options without opening PRs",
        "repository-dependency-reviewer": "Review local dependency manifests with read-only file inspection and Endor evidence",
        "sca-remediation": "Remediate dependency vulnerabilities with Endor SCA findings, UIA evidence, low-risk PR lanes, deterministic risk decisions, validation, and approved PR/MR creation",
        "vulnerability-explainer": "Understand a specific CVE, GHSA, or Endor vulnerability and what to do next",
    }
    return summaries.get(agent_id, "Use an Endor Labs workflow agent")


def _agent_example(agent_id: str) -> str:
    examples = {
        "ai-sast-triage": "@agent-ai-sast-triage triage AI SAST findings for this repository",
        "dependency-decision-helper": "@agent-dependency-decision-helper assess npm lodash version 4.17.20",
        "upgrade-impact-analysis": "@agent-upgrade-impact-analysis show the safest upgrade path for repository <owner>/<repo> package lodash",
        "package-risk-summary": "@agent-package-risk-summary summarize npm lodash version 4.17.20",
        "remediation-planner": "@agent-remediation-planner preview remediation options for this repository",
        "repository-dependency-reviewer": "@agent-repository-dependency-reviewer review this repository's dependency manifests",
        "sca-remediation": "@agent-sca-remediation check this repository for P0 SCA findings I can start remediating",
        "vulnerability-explainer": "@agent-vulnerability-explainer explain CVE-2021-44228",
    }
    return examples.get(agent_id, f"@agent-{agent_id} help")


def _claude_code_edition_readme(
    recipe: EndorAgentRecipe,
    edition: str,
    *,
    has_architecture: bool = False,
    show_edition_name: bool = True,
) -> str:
    name = _edition_name(edition)
    title = f"{recipe.name} {name}" if show_edition_name else recipe.name
    artifact_label = "edition" if show_edition_name else "agent"
    if recipe.safety_class == "mutating":
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor tenant access through authenticated `endorctl api` or documented Endor API credentials.",
            "A local workspace checkout for any repository the agent will patch.",
            "Git and source-provider credentials that can push a branch and open the requested pull request or merge request.",
        ]
        if recipe.id == "ai-sast-triage":
            requirements.extend(
                [
                    "GitHub or GitLab credentials that can read PR/MR reviews and comments from the target repository.",
                    "A configured AppSec approver list when the agent is allowed to create Endor exception policies in standalone mode.",
                    "Endor policy-write access for direct exception-policy creation after verified AppSec approval.",
                ]
            )
        workflow_label = {
            "ai-sast-triage": "AI SAST triage",
            "sca-remediation": "SCA remediation",
        }.get(recipe.id, recipe.name)
        notes = [
            f"This {artifact_label} preserves the {workflow_label} workflow capabilities as a mutating agent.",
            "The agent may fetch source context, prepare patches, edit files, run commands, open a change request, verify AppSec approval evidence, and create an Endor exception policy when the workflow requires it.",
            "Confirm repository and branch targets before allowing write or pull-request actions. Confirm the rendered Endor policy spec before allowing exception-policy creation.",
        ]
        if recipe.id == "sca-remediation":
            notes = [
                f"This {artifact_label} preserves the SCA remediation workflow capabilities as a mutating agent.",
                "The agent may query Endor SCA findings and VersionUpgrade/UIA evidence, list separate non-breaking low-risk PR-ready candidates, inspect local manifests, produce a deterministic risk_decision, prepare dependency changes, run validation, open a change request, and post a remediation comment when approved.",
                "Confirm the selected package, UIA evidence, risk_decision, target files, generated diff, validation status, branch, and PR/MR body before allowing mutations.",
            ]
        if recipe.action_contracts_path:
            notes.append(
                "`actions.yaml` lists the semantic side effects and any external adapter requirements."
            )
    elif edition == "developer-edition" or not _allows_read_only_endorctl(recipe):
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor MCP access through the subagent's bundled MCP server config.",
            f"No shell access or authenticated endorctl setup is required for this {artifact_label}.",
        ]
        if recipe.host_capabilities_required.read_files:
            requirements.insert(2, "Read-only access to dependency manifests in the target workspace.")
        notes = [
            (
                f"This {artifact_label} uses Endor MCP tools plus Claude Code read-only file inspection."
                if recipe.host_capabilities_required.read_files
                else f"This {artifact_label} uses Endor MCP tools only."
            ),
            "It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.",
        ]
    else:
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        if _uses_mcp(recipe):
            requirements.insert(
                1,
                "Endor MCP access through the subagent's bundled MCP server config.",
            )
        notes = [
            (
                f"This {artifact_label} uses MCP first, then read-only endorctl api lookups for richer signals."
                if _uses_mcp(recipe)
                else f"This {artifact_label} uses read-only endorctl api lookups and does not require Endor MCP."
            ),
            "Bash use is limited by prompt to the documented Endor lookup commands.",
        ]

    architecture = _architecture_readme_section(recipe) if has_architecture else []
    return "\n".join([
        f"# {title}",
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
        *_claude_code_agent_setup_section(recipe),
        "## Example",
        "",
        "```text",
        _example_prompt(recipe, edition),
        "```",
        "",
        *_claude_code_example_workflow_section(recipe),
        *_claude_code_smoke_test_section(recipe),
        *architecture,
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def _claude_code_agent_setup_section(
    recipe: EndorAgentRecipe,
) -> list[str]:
    if recipe.id == "sca-remediation":
        return [
            "## Setup Checklist",
            "",
            "### 1. Install The Subagent",
            "",
            "Run this from the target repository where Claude Code will operate:",
            "",
            "```bash",
            "mkdir -p .claude/agents",
            "cp /path/to/endor-labs-agent-kit/claude-code/sca-remediation/sca-remediation.md \\",
            "  .claude/agents/sca-remediation.md",
            "```",
            "",
            "### 2. Verify Local Access",
            "",
            "Run the checks that match your source provider:",
            "",
            "```bash",
            "git remote -v",
            "endorctl --version",
            "endorctl host-check",
            "gh auth status        # GitHub repositories",
            "glab auth status      # GitLab repositories",
            "```",
            "",
            "Claude Code does not need an Endor MCP server for this agent. If `endorctl`,",
            "direct Endor API credentials, local dependency-manager tooling, or",
            "source-provider credentials are not authenticated, the agent should report",
            "the missing setup in `data_gaps`.",
            "",
            "### 3. Prepare For Approval Gates",
            "",
            "The agent shows UIA evidence, risk_decision, target files, diff,",
            "validation plan, branch, and PR/MR body before mutating. Approve file",
            "edits and PR/MR creation as separate steps.",
            "",
            "Validation commands are selected from the repository's actual package",
            "manager and build metadata. The agent should not assume a Maven, npm,",
            "Python, Go, .NET, Ruby, Rust, or any other ecosystem layout until it",
            "has inspected the local manifests and documented build instructions.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Setup Checklist",
        "",
        "### 1. Install The Subagent",
        "",
        "Run this from the target repository where Claude Code will operate:",
        "",
        "```bash",
        "mkdir -p .claude/agents",
        "cp /path/to/endor-labs-agent-kit/claude-code/ai-sast-triage/ai-sast-triage.md \\",
        "  .claude/agents/ai-sast-triage.md",
        "```",
        "",
        "Or ask an LLM with filesystem access to do it:",
        "",
        "```text",
        "Install the Endor Labs AI SAST Triage agent in this repository.",
        "",
        "Agent Kit root: /path/to/endor-labs-agent-kit",
        "Agent artifact: claude-code/ai-sast-triage/ai-sast-triage.md",
        "Install path: .claude/agents/ai-sast-triage.md",
        "",
        "Preserve the generated agent prompt exactly. After installing it, check",
        "endorctl, git remote, and GitHub/GitLab CLI access, then tell",
        "me the exact prompt to invoke the agent.",
        "```",
        "",
        "### 2. Verify Local Access",
        "",
        "Run the checks that match your source provider:",
        "",
        "```bash",
        "git remote -v",
        "endorctl --version",
        "gh auth status        # GitHub repositories",
        "glab auth status      # GitLab repositories",
        "```",
        "",
        "Claude Code does not need an Endor MCP server for this agent. If `endorctl`,",
        "direct Endor API credentials, or source-provider credentials are not",
        "authenticated, the agent should report the missing setup in `data_gaps`.",
        "",
        "### 3. Understand Finding Evidence",
        "",
        "When Endor AI SAST includes `## Exploit Reproduction`, the agent uses it",
        "for priority, confidence, and safe local validation planning. It must not",
        "run exploit steps against live systems or paste weaponized detail into a",
        "PR/MR body.",
        "",
        "When Endor AI SAST includes `## Remediation Guidance`, the agent uses it as",
        "patch context. It can apply the guidance as-is, adapt it to the codebase,",
        "or reject it with a reason when the pinned source or tests show a safer fix.",
        "",
        "### 4. Match The AURI PR/MR Body",
        "",
        "Remediation PR/MR bodies should follow the AURI AI SAST structure:",
        "",
        "- `## 🛡️ Endor Labs AURI Security Fix: <finding title>`",
        "- hidden `<!-- auri:ai-sast-context ... -->` finding/project metadata",
        "- `### 🔧 What changed`",
        "- `### 🔎 Evidence provided by AURI`",
        "- `### ✅ Review checklist`",
        "- `### 📝 Need an exception instead?` with standalone Agent Kit request prompts",
        "- folded `📎 Finding details` table",
        "",
        "Severity must be visually indicated everywhere it is shown: Critical `🔴`,",
        "High `🟠`, Medium `🟡`, and Low `🟢`.",
        "Default to one remediation PR/MR per AI SAST finding so review, validation,",
        "rollback, and exception handling stay traceable. Group findings only when",
        "one small, cohesive source change fixes the same root cause in the same",
        "repository/component or when the user explicitly asks for grouping.",
        "The PR/MR title should start with the visual indicator and highest severity",
        "represented, such as `🟡 Medium: Fix ...` for one finding or",
        "`🟠 High: Fix 3 AI SAST findings` for a tightly grouped fix. Bracket-only",
        "titles like `[Medium] Fix ...` should be treated as invalid.",
        "",
        "When `endor-agent-kit` is available and temporary file writes are allowed,",
        "use it as the source of truth for generated bodies: validate the normalized",
        "AI SAST JSON, render the PR/MR body, and lint the rendered body before",
        "opening the change request.",
        "",
        "### 5. Configure Optional AppSec Approvers",
        "",
        "The exception workflow is optional. You can use the agent for triage and",
        "remediation PR/MRs without configuring AppSec approvers or Endor policy-write",
        "access. If your team wants PR/MR-driven exceptions, standalone exception",
        "creation requires an approval artifact in the PR/MR. Give the agent the",
        "allowed approvers before it creates an Endor exception policy. Use GitHub",
        "handles, GitLab usernames, or team slugs:",
        "",
        "```text",
        "AppSec approvers: @alice, @bob, @endor-labs/appsec",
        "```",
        "",
        "The developer requesting the exception must not approve their own request.",
        "",
        "### 6. Approval Comment Format",
        "",
        "When the agent requests an exception, an AppSec approver should comment or",
        "review with one of these exact forms:",
        "",
        "```text",
        "APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>",
        "APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        "```",
        "",
        "The agent verifies the approver, finding UUID, request type, and expiration",
        "before it renders the Endor policy spec. In standalone Agent Kit, PR/MR comments are approval evidence only; they do not automatically trigger a",
        "policy write unless a user or external automation invokes the installed",
        "agent.",
        "",
        "### 7. Optional Policy Creation Gate",
        "",
        "The agent may create a scoped Endor exception policy only after all of these",
        "are true:",
        "",
        "- AppSec approval evidence is verified from the PR/MR.",
        "- Existing Endor policies are checked by generated policy name and finding UUID.",
        "- The policy spec is shown in the Claude Code session.",
        "- The user explicitly confirms policy creation.",
        "- Endor returns a policy UUID.",
        "",
        "If an active matching exception policy already exists for the same finding,",
        "project, and reason, the agent should reuse that policy and should not",
        "create a duplicate. The PR/MR decision comment should show the policy name",
        "first, keep the policy UUID for API traceability, and display a human-readable",
        "Endor project label instead of raw `$uuid=...` selector syntax.",
        "",
    ]


def _claude_code_example_workflow_section(recipe: EndorAgentRecipe) -> list[str]:
    if recipe.id == "sca-remediation":
        return [
            "## Example Workflow",
            "",
            "Use these copy/paste prompts after the agent is installed.",
            "",
            "### 1. Rank Without Mutating",
            "",
            "```text",
            "@agent-sca-remediation check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR. Rank package-level fixes and show the UIA evidence for the best first fix.",
            "```",
            "",
            "### 2. List Other Low-Risk PRs",
            "",
            "```text",
            "@agent-sca-remediation show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and the risky solver. Do not edit files, create branches, push, or open a PR/MR.",
            "```",
            "",
            "### 3. Prepare One Patch",
            "",
            "```text",
            "@agent-sca-remediation prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
            "```",
            "",
            "### 4. Open The PR/MR After Approval",
            "",
            "```text",
            "@agent-sca-remediation apply the approved patch, run local validation, and then ask me before pushing a branch or opening the PR/MR. Use the AURI-style PR/MR body with emoji sections, UIA evidence, validation status, and a folded advisory/finding list.",
            "```",
            "",
            "Do not call a high-count finding bucket low risk unless the response shows",
            "the actual VersionUpgrade/UIA evidence. Prefer a package-level fix when one",
            "package upgrade clears findings across multiple manifests. Future PR/MR bodies",
            "should include the folded `Advisories This Upgrade Fixes` section, and should",
            "scope compatibility claims to Endor UIA/CIA plus validation that actually ran.",
            "If CIA is indeterminate or risk is medium/high, the agent should produce a",
            "deterministic `risk_decision` from Endor evidence plus local source usage",
            "instead of recommending a manual release-note skim.",
            "The selection/plan gate is not complete until that `risk_decision` is",
            "present; low UIA risk, zero conflicts, and a simple manifest edit are",
            "inputs to the verdict, not replacements for it.",
            "Keep low-risk non-breaking UIA candidates separate from P0/exploited",
            "findings and from the risky solver. Hidden P0 duplicates should be",
            "reported separately and excluded from `most_findings_in_one_pr`.",
            "Choose validation commands from the repository's actual ecosystem and",
            "manifest layout; do not carry Maven or any other package-manager",
            "commands across runs unless the current repository proves that layout.",
            "Use the branch convention `remediation/sca/<package>-<target-version>`",
            "unless the user explicitly asks for a different branch name.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Example Workflow",
        "",
        "Use these copy/paste prompts after the agent is installed. Replace the",
        "placeholders with the finding UUID, PR/MR URL, date, and AppSec approvers",
        "from your environment.",
        "",
        "### 1. Triage Without Mutating",
        "",
        "```text",
        "@agent-ai-sast-triage triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.",
        "```",
        "",
        "### 2. Open One Remediation PR",
        "",
        "```text",
        "@agent-ai-sast-triage remediate finding <finding_uuid> for this repository. Use Endor Exploit Reproduction and Remediation Guidance as context, but verify the fix against the source. Show me the patch, branch name, PR/MR title, and PR/MR body before pushing. After I approve, open exactly one PR/MR.",
        "```",
        "",
        "Use one PR/MR per finding by default. If a single cohesive source change",
        "fixes several findings with the same root cause, use the highest severity",
        "in the title, for example `🟠 High: Fix 3 AI SAST findings`, and list each",
        "finding separately in the body.",
        "",
        "### 3. Request Optional Exception Approval",
        "",
        "This workflow is optional; use it only when the finding should be excepted",
        "instead of remediated in code.",
        "",
        "```text",
        "@agent-ai-sast-triage request an AppSec exception review for finding <finding_uuid> on PR/MR <pr_or_mr_url>. Request type: accept risk until YYYY-MM-DD. Reason: <owner, mitigation, and why code will not change now>. Allowed AppSec approvers: @alice, @bob. Do not create an Endor policy yet. Post or update a PR/MR comment with the exact approval phrase the approver can use.",
        "```",
        "",
        "### 4. AppSec Approval Comment",
        "",
        "An allowed AppSec approver can use one of these comments or review bodies:",
        "",
        "```text",
        "APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>",
        "APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        "```",
        "",
        "The requester, PR author, and agent account must not approve their own",
        "exception request.",
        "",
        "### 5. Optional Scoped Endor Exception Policy",
        "",
        "```text",
        "@agent-ai-sast-triage verify AppSec approval on PR/MR <pr_or_mr_url> for finding <finding_uuid>. Allowed AppSec approvers: @alice, @bob. If approval is valid and not self-approval, check for an existing active Endor exception policy for this finding/project/reason, then render the Endor exception policy spec for my confirmation. After I confirm, create or reuse the scoped policy and comment on the PR/MR with the policy name, policy UUID, Endor project, approver, expiration, and evidence URL.",
        "```",
        "",
        "For render-only exception checks, the agent should emit validator-ready",
        "JSON with `approvals[].approved: true`, `approvals[].expiration_time`,",
        "`exception_policies[].policy_name`, `exception_policies[].idempotency_check`,",
        "and `exception_policies[].policy_spec`. A pending policy should fail only",
        "the explicit-confirmation gate until the user approves the Endor write.",
        "",
        "Do not combine remediation and exception approval in normal production use.",
        "If you test both paths for QA, label the exception as temporary validation.",
        "Redact concrete exploit payloads from PR/MR prose and comments.",
        "",
    ]


def _codex_readme(recipe: EndorAgentRecipe, *, has_architecture: bool = False) -> str:
    if recipe.safety_class == "mutating":
        requirements = [
            "Codex with filesystem and terminal access to the target repository.",
            "Endor tenant access through authenticated `endorctl api` or documented Endor API credentials.",
            "Git and source-provider credentials for approved branch, PR/MR, review, or comment workflows.",
        ]
        if recipe.id == "ai-sast-triage":
            requirements.extend(
                [
                    "A configured AppSec approver list before standalone exception-policy creation.",
                    "Endor policy-write access only after verified AppSec approval and explicit user confirmation.",
                ]
            )
    else:
        requirements = [
            "Codex with access to the current workspace.",
            "The Endor access path declared by the recipe.",
            "No mutating repository, source-provider, or Endor writes for this skill.",
        ]
    return "\n".join(
        [
            f"# {recipe.name} Codex Skill",
            "",
            recipe.description.strip(),
            "",
            "## Install",
            "",
            "Copy this generated skill directory into your Codex skills directory:",
            "",
            "```bash",
            "mkdir -p \"${CODEX_HOME:-$HOME/.codex}/skills\"",
            f"cp -R /path/to/endor-labs-agent-kit/codex/{recipe.id} \\",
            f"  \"${{CODEX_HOME:-$HOME/.codex}}/skills/{recipe.id}\"",
            "```",
            "",
            "Start a new Codex session after installing or replacing the skill.",
            "",
            "## Requirements",
            "",
            *[f"- {item}" for item in requirements],
            "",
            "## Example",
            "",
            "```text",
            _codex_example_prompt(recipe),
            "```",
            "",
            *_codex_example_workflow_section(recipe),
            *_codex_smoke_test_section(recipe),
            *(_codex_architecture_readme_section(recipe) if has_architecture else []),
            "## Notes",
            "",
            "- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.",
            "- `actions.yaml` records semantic side-effect contracts when the recipe declares mutating actions.",
            "- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.",
            "",
        ]
    )


def _codex_example_prompt(recipe: EndorAgentRecipe) -> str:
    if recipe.id == "ai-sast-triage":
        return "Use the ai-sast-triage skill to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy unless I approve the specific gate."
    if recipe.id == "sca-remediation":
        return "Use the sca-remediation skill to check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR until I approve."
    return f"Use the {recipe.id} skill to help with this Endor Labs workflow."


def _codex_architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    return [_codex_text(line) for line in _architecture_readme_section(recipe)]


def _codex_text(text: str) -> str:
    return (
        text.replace("Claude Code session", "Codex session")
        .replace("Claude Code artifact", "Codex skill")
        .replace("Claude Code agent", "Codex skill")
        .replace("Claude Code runs", "Codex runs")
        .replace("Claude Code", "Codex")
    )


def _codex_example_workflow_section(recipe: EndorAgentRecipe) -> list[str]:
    if recipe.id == "sca-remediation":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use the sca-remediation skill to show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and risky solver. Do not edit files, create branches, push, or open a PR/MR.",
            "```",
            "",
            "```text",
            "Use the sca-remediation skill to prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
            "```",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Example Workflow",
        "",
        "```text",
        "Use the ai-sast-triage skill to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.",
        "```",
        "",
        "```text",
        "Use the ai-sast-triage skill to remediate finding <finding_uuid> for this repository. Use Endor Exploit Reproduction and Remediation Guidance as context, but verify the fix against the source. Show me the patch, branch name, PR/MR title, and PR/MR body before pushing. After I approve, open exactly one PR/MR.",
        "```",
        "",
        "Use the exception workflow only when a finding should be excepted instead",
        "of remediated in code.",
        "",
        "```text",
        "Use the ai-sast-triage skill to verify AppSec approval on PR/MR <pr_or_mr_url> for finding <finding_uuid>. Allowed AppSec approvers: @alice, @bob. If approval is valid and not self-approval, check for an existing active Endor exception policy for this finding/project/reason, then render the Endor exception policy spec for my confirmation. After I confirm, create or reuse the scoped policy and comment on the PR/MR with the policy name, policy UUID, Endor project, approver, expiration, and evidence URL.",
        "```",
        "",
    ]


def _codex_smoke_test_section(recipe: EndorAgentRecipe) -> list[str]:
    if recipe.id not in {"ai-sast-triage", "sca-remediation"}:
        return []
    return [
        "## QA Smoke Test",
        "",
        "Use a fresh Codex session after installing the skill. Run a planning-only",
        "prompt first and verify the response references the Codex skill, preserves",
        "approval gates, and does not claim file edits, PR/MR creation, comments, or",
        "Endor policy writes.",
        "",
    ]


def _managed_agents_edition_readme(
    recipe: EndorAgentRecipe,
    edition: str,
    *,
    has_architecture: bool = False,
    show_edition_name: bool = True,
) -> str:
    name = _edition_name(edition)
    title = f"{recipe.name} {name}" if show_edition_name else recipe.name
    artifact_label = "edition" if show_edition_name else "agent"
    if edition == "developer-edition" or not _allows_read_only_endorctl(recipe):
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "A remote Endor MCP server URL configured in agent.yaml.",
            "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            f"No pre-built Bash or filesystem tools are enabled for this {artifact_label}.",
        ]
        notes = [
            f"This {artifact_label} uses the Managed Agents MCP connector only.",
            "The generated `agent.yaml` intentionally uses a placeholder MCP URL that must be replaced.",
            "Unavailable MCP, vault, auth, or account-tier signals are reported in data_gaps.",
        ]
    else:
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        if _uses_mcp(recipe):
            requirements[1:1] = [
                "A remote Endor MCP server URL configured in agent.yaml.",
                "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            ]
        notes = [
            (
                f"This {artifact_label} uses MCP first, then read-only endorctl api lookups for richer signals."
                if _uses_mcp(recipe)
                else f"This {artifact_label} uses read-only endorctl api lookups and does not require Endor MCP."
            ),
            "The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.",
            "Bash use remains limited by prompt to the documented Endor lookup commands.",
        ]

    architecture = _architecture_readme_section(recipe) if has_architecture else []
    return "\n".join([
        f"# {title}",
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
        *architecture,
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def _architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    body = {
        "ai-sast-triage": (
            "In Agent Kit, PR/MR creation is host-mediated. Claude Code runs in the target "
            "checkout, gathers Endor evidence including exploit reproduction and remediation "
            "guidance when present, applies the confirmed diff locally, creates and pushes a "
            "branch, then opens the change request with configured source-provider credentials. "
            "If the host cannot perform one of those steps, the agent must stop and report the "
            "missing capability in `data_gaps`."
        ),
        "upgrade-impact-analysis": (
            "This read-only agent resolves a human project selector to the Endor project used "
            "for VersionUpgrade queries. Claude Managed Agents do not inspect local git by "
            "default, so sessions should provide a repository URL, owner/repo, or Endor "
            "project name instead of requiring a project UUID."
        ),
        "remediation-planner": (
            "This dry-run workflow resolves project or finding context, gathers Endor "
            "remediation evidence, and returns a plan only. It does not edit files, push "
            "branches, or open PRs/MRs."
        ),
        "sca-remediation": (
            "This mutating Claude Code agent resolves repository context, queries Endor "
            "SCA findings, requires VersionUpgrade/UIA evidence before recommending a "
            "best first fix, keeps non-breaking low-risk UIA PR candidates separate "
            "from the P0/exploited queue and risky solver, resolves risky or "
            "CIA-indeterminate upgrades into a deterministic risk_decision, prepares "
            "local dependency changes, runs ecosystem-appropriate validation when "
            "possible, and opens a PR/MR only after explicit approval. "
            "It does not use or require an Endor MCP server."
        ),
    }.get(
        recipe.id,
        "This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.",
    )
    return [
        "## Architecture",
        "",
        f"![{recipe.name} architecture](architecture.svg)",
        "",
        body,
        "",
    ]


def _claude_code_smoke_test_section(recipe: EndorAgentRecipe) -> list[str]:
    if recipe.id == "sca-remediation":
        return [
            "## QA Smoke Test",
            "",
            "When validating this agent, isolate the run from user-level Claude skills so",
            "the result proves the Agent Kit artifact itself is doing the work.",
            "",
            "```bash",
            "export CLAUDE_CONFIG_DIR=\"$(mktemp -d)\"",
            "claude -p --agent sca-remediation --permission-mode bypassPermissions \\",
            "  \"Check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve.\"",
            "```",
            "",
            "The run log should not reference user-level skills or Endor MCP tooling.",
            "If it does, the test is contaminated and should be rerun in a clean",
            "Claude configuration.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## QA Smoke Test",
        "",
        "When validating this agent, isolate the run from user-level Claude skills so",
        "the result proves the Agent Kit artifact itself is doing the work.",
        "",
        "```bash",
        "export CLAUDE_CONFIG_DIR=\"$(mktemp -d)\"",
        "claude -p --agent ai-sast-triage --permission-mode bypassPermissions \\",
        "  \"Triage AI SAST findings for this repository. Do not open a PR until I approve the patch.\"",
        "```",
        "",
        "The run log should not reference user-level skills such as",
        "`~/.claude/skills/endor-ai-sast`. If it does, the test is contaminated",
        "and should be rerun in a clean Claude configuration.",
        "",
    ]


def _edition_name(edition: str) -> str:
    if edition == "developer-edition":
        return "Developer Edition"
    if edition == "enterprise-edition":
        return "Enterprise Edition"
    raise ValueError(f"Unknown edition {edition!r}")


def _example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    input_names = {field.name for field in recipe.inputs}
    if recipe.id == "ai-sast-triage":
        return f"@agent-{recipe.id} triage AI SAST findings for this repository. Do not open a PR until I approve the patch."
    if recipe.id == "sca-remediation":
        return f"@agent-{recipe.id} check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve."
    if recipe.id == "remediation-planner":
        return f"@agent-{recipe.id} preview remediation options for this repository"
    if "vulnerability_id" in input_names:
        return f"@agent-{recipe.id} explain CVE-2021-44228"
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return f"@agent-{recipe.id} assess npm lodash from 4.17.20 to 4.17.21"
        return f"@agent-{recipe.id} show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA and manifest files"
    if recipe.id == "package-risk-summary":
        return f"@agent-{recipe.id} summarize npm lodash version 4.17.20"
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return f"@agent-{recipe.id} assess npm lodash version 4.17.20"
    return f"@agent-{recipe.id} help"


def _managed_example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    input_names = {field.name for field in recipe.inputs}
    if recipe.id == "ai-sast-triage":
        return "Triage AI SAST findings for this repository. Do not open a PR until I approve the patch."
    if recipe.id == "remediation-planner":
        return "Preview remediation options for repository <owner>/<repo>."
    if "vulnerability_id" in input_names:
        return "Explain CVE-2021-44228."
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return "Assess upgrading npm lodash from 4.17.20 to 4.17.21."
        return "Show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA, findings fixed, manifest files, and breaking changes."
    if recipe.id == "package-risk-summary":
        return "Summarize npm lodash version 4.17.20."
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return "Assess npm lodash version 4.17.20."
    return "Help me use this Endor Labs agent."
