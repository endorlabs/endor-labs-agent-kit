"""Portable Host Adapter for runtime-neutral artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.compilers.portable import (
    HOST,
    assert_portable_text,
    compile_portable_prepared,
    portable_text,
    render_portable_actions_yaml,
)
from endor_agent_kit.compilers.raw import compile_raw_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.portable_runtime_conformance import PORTABLE_UNTRUSTED_CONTENT_RULE
from endor_agent_kit.recipe import EndorAgentRecipe
from endor_agent_kit.safety_posture import source_recipe_safety_posture

from .readme import agent_readme_start_here
from .records import (
    BundleRecord,
    artifact_bundle_record,
    prepared_actions_source,
    prepared_architecture_source,
)


class PortableHostAdapter:
    """Publish portable runtime-neutral agent bundles."""

    host = HOST

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one portable Host Artifact Bundle."""

        compile_raw_prepared(prepared)
        compile_portable_prepared(prepared)

        recipe_file = prepared.path
        recipe = prepared.recipe
        agent_root = destination / HOST / recipe.id
        if agent_root.exists():
            shutil.rmtree(agent_root)
        agent_root.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        source_dir = recipe_file.parent / "dist" / HOST / recipe.id
        for filename in ("agent.md", "agent.manifest.json", "output-contract.md"):
            artifact = agent_root / filename
            shutil.copyfile(source_dir / filename, artifact)
            written.append(artifact)

        architecture = prepared_architecture_source(prepared)
        has_architecture = architecture.is_file()
        readme = agent_root / "README.md"
        readme.write_text(portable_readme(recipe, has_architecture=has_architecture), encoding="utf-8")
        written.append(readme)

        if has_architecture:
            published_architecture = agent_root / "architecture.svg"
            architecture_content = portable_text(architecture.read_text(encoding="utf-8"))
            assert_portable_text("architecture.svg", architecture_content)
            published_architecture.write_text(architecture_content, encoding="utf-8")
            written.append(published_architecture)

        actions = prepared_actions_source(prepared)
        if actions.is_file():
            published_actions = agent_root / "actions.yaml"
            actions_content = render_portable_actions_yaml(prepared.actions)
            published_actions.write_text(actions_content, encoding="utf-8")
            written.append(published_actions)

        if _needs_endorctl_setup(recipe):
            setup = agent_root / "endorctl-setup.md"
            setup_content = portable_text(
                (recipe_file.parent / "dist" / "raw" / "endorctl-setup.md").read_text(
                    encoding="utf-8"
                )
            )
            assert_portable_text("endorctl-setup.md", setup_content)
            setup.write_text(setup_content, encoding="utf-8")
            written.append(setup)

        return BundleRecord(
            host=HOST,
            written=tuple(written),
            manifest_records=(
                artifact_bundle_record(
                    destination,
                    recipe,
                    HOST,
                    "portable-agent",
                    "Portable Agent Bundle",
                    agent_root,
                    requires_endorctl=recipe.requires_endorctl
                    if _needs_endorctl_setup(recipe)
                    else "",
                ),
            ),
        )


def portable_readme(recipe: EndorAgentRecipe, *, has_architecture: bool = False) -> str:
    """Render the portable Generated Agent README."""

    setup_files = [
        "`agent.md`: generated runtime-neutral agent instructions.",
        "`agent.manifest.json`: machine-readable runtime contract.",
        "`output-contract.md`: inputs, outputs, adapter contract summary, and workflow gates.",
        "`runtime/summarize_endor_artifact.py`: deterministic large-result integrity summary helper.",
    ]
    if recipe.action_contracts_path:
        setup_files.append("`actions.yaml`: portable action contracts for adapter implementers.")
    if _needs_endorctl_setup(recipe):
        setup_files.append("`endorctl-setup.md`: Endor runtime setup notes.")
    if has_architecture:
        setup_files.append("`architecture.svg`: human-readable workflow diagram.")
    if recipe.policy_pack_support:
        setup_files.append(
            "`policy-packs/` in the catalog root: optional templates and examples for trusted runtime policy configuration."
        )

    architecture = _portable_architecture_readme_section(recipe) if has_architecture else []
    start_here = agent_readme_start_here(
        recipe,
        host_label="portable runtime",
        artifact_label="agent bundle",
        install_summary="Load `agent.md` and `agent.manifest.json` into your runtime and wire only the adapters your policy allows.",
        run_summary=f"Use this agent to analyze repository <repo> with `{recipe.id}`.",
        has_architecture=has_architecture,
    )
    return "\n".join(
        [
            f"# {recipe.name} Portable Agent Bundle",
            "",
            portable_text(recipe.description).strip(),
            "",
            *start_here,
            "## Use This When",
            "",
            "Use this bundle when your organization already has an agent runtime, source-provider workflow, ticketing workflow, approval system, credential controls, and audit pipeline. The bundle supplies the generated agent and runtime contract; your platform supplies adapters.",
            "",
            "## Bundle Files",
            "",
            *[f"- {item}" for item in setup_files],
            "",
            "## Runtime Responsibilities",
            "",
            "- Load `agent.md` as generated instructions without editing it.",
            "- Read `agent.manifest.json` to discover required transports, capabilities, declared actions, and runtime wrappers.",
            "- Provide Endor MCP or Endor API transports declared by the manifest.",
            "- Provide repository, source-provider, approval, ticketing, and Endor write adapters only when authorized by your platform policy.",
            "- Load trusted Agent Policy Packs from runtime or protected workspace configuration when configured.",
            "- Pause for confirmation before any action where `confirmation_required` is true.",
            "- Return structured evidence after adapter execution, or return a data gap when the adapter, credential, permission, or transport is unavailable.",
            f"- {PORTABLE_UNTRUSTED_CONTENT_RULE}",
            "- Fail closed to plan-only output or `data_gaps` when approvals, permissions, or adapter evidence are missing.",
            "",
            "## Security Model",
            "",
            "Agent Kit defines the workflow, safety contract, and evidence requirements. Your runtime enforces tenant access, repository permissions, ticket or change-request permissions, approval policy, logging, audit, and adapter authorization. The agent must not improvise around missing permissions; the runtime should return a structured data gap instead.",
            "",
            "For a complete integration checklist, see `docs/portable-runtime-conformance.md` in the Agent Kit repository.",
            "",
            "## Example Adapter Mappings",
            "",
            "These examples are illustrative, not requirements.",
            "",
            "| Portable action | Example runtime adapters |",
            "| --- | --- |",
            "| `endor.query` | `endorctl agent api --agent-id <canonical-recipe-id>`, approved Endor MCP adapter |",
            "| `source.change_request.create` | GitHub pull request, GitLab merge request, Bitbucket pull request, internal change workflow |",
            "| `ticket.create` | Jira issue, ServiceNow task, Linear issue, internal ticketing |",
            "| `approval.verify` | AppSec approval service, source-provider approval API, internal risk-acceptance workflow |",
            "| `endor.policy.write` | Endor API proxy, approved policy-write service |",
            "",
            "## Example Runtime Invocation",
            "",
            "```text",
            "System:",
            "Load portable/<agent>/agent.md as the generated instruction source.",
            "Expose only the adapters allowed by portable/<agent>/agent.manifest.json and your organization policy.",
            "When the agent requests an action, pause for approval if confirmation_required=true.",
            "After execution, return adapter evidence to the agent.",
            "",
            "User:",
            "Use this agent to analyze repository <repo>. Prefer ticket creation over a source change request unless the plan is low risk and validation evidence is available.",
            "```",
            "",
            "## Workflow Target Guidance",
            "",
            "For remediation workflows, let the agent produce the remediation plan first. At the mutation gate, your runtime can offer approved targets such as plan-only output, source change request creation, ticket creation, or both. `ticket.create` is available as a runtime wrapper in portable bundles unless a recipe explicitly declares ticket creation as an agent-owned action.",
            "",
            "## Drift Check",
            "",
            "After copying this bundle into your runtime, compare it with the catalog manifest:",
            "",
            "```bash",
            f"endor-agent-kit check-install --host portable --agent {recipe.id} --portable-dir /path/to/runtime/agents/{recipe.id}",
            "```",
            "",
            *architecture,
            "## Generated Artifact Policy",
            "",
            "`agent.md` and sibling contract files are generated. Configure runtime adapters and organization policy outside this bundle. If agent behavior must change, update the Source Recipe and regenerate the catalog.",
            "",
        ]
    )


def _needs_endorctl_setup(recipe: EndorAgentRecipe) -> bool:
    return source_recipe_safety_posture(recipe).requires_endorctl_setup


def _portable_architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    return [
        "## Architecture",
        "",
        f"![{recipe.name} architecture](architecture.svg)",
        "",
        "The diagram is included for human review of workflow boundaries, adapter responsibilities, and external systems. Runtime ingestion can ignore this file when only text and JSON contracts are supported.",
        "",
    ]
