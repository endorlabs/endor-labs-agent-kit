"""Lifecycle handoff artifacts for Agent Kit source validation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Sequence

from endor_agent_kit.evidence_plans import compile_evidence_plans
from endor_agent_kit.knowledge_pack import default_task_profile_for_agent, load_knowledge_pack
from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.publication.plugin_package_common import PLUGIN_NAME, package_version
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.recipe import EndorAgentRecipe, load_recipe
from endor_agent_kit.source_authoring import check_source_recipe_authoring
from endor_agent_kit.structured_output_contracts import STRUCTURED_OUTPUT_CONTRACTS, required_fields_for
from endor_agent_kit.validator import validate_recipe_file

VALIDATION_REQUEST_KIND = "endor-agent-kit.validation-request"
VALIDATION_REQUEST_SCHEMA_VERSION = 1
SOURCE_ONLY_ROOT_SKILLS = frozenset({"create-endor-labs-agent"})
GENERATED_SURFACES = (
    "README.md",
    "manifest.json",
    ".agents/plugins",
    ".claude-plugin",
    ".cursor-plugin",
    "agents",
    "assets",
    "claude-code",
    "claude-managed-agents",
    "codex",
    "cursor-sdk",
    "gemini",
    "plugins",
    "portable",
    "runtime",
)


def prepare_validation_request(
    *,
    repo_root: Path,
    output: Path,
    agents: Sequence[str] = (),
    scope: str = "changed",
    base_ref: str = "origin/main",
    dest: Path | None = None,
    regenerate: bool = False,
) -> dict[str, Any]:
    """Write a public-neutral validation request for private QA consumers."""

    repo = repo_root.resolve()
    catalog_root = (dest or repo_root).resolve()
    recipe_paths = _selected_recipe_paths(repo, agents=agents, scope=scope, base_ref=base_ref)
    all_recipe_paths = _all_recipe_paths(repo)
    warnings: list[str] = []
    errors: list[str] = []

    if not recipe_paths:
        errors.append("No source agents selected. Pass --agent or use --scope release-candidate/all.")

    regenerated = False
    if regenerate:
        publish_recipes(all_recipe_paths, catalog_root, prune=True, include_plugins=True)
        regenerated = True

    generated_state = generated_artifact_state(repo, all_recipe_paths=all_recipe_paths)
    if not generated_state["current"]:
        warnings.append(
            "Generated artifacts are stale; rerun with --regenerate or run "
            "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins"
        )

    git_state = _git_state(repo, base_ref=base_ref)
    if git_state["dirty"]:
        warnings.append("Working tree is dirty; validation request is for development evidence only.")

    agent_entries = []
    for recipe_path in recipe_paths:
        entry = _agent_entry(repo, recipe_path, base_ref=base_ref)
        agent_entries.append(entry)
        errors.extend(entry["errors"])
        warnings.extend(entry["warnings"])

    publishable = (
        not git_state["dirty"]
        and generated_state["current"]
        and not errors
    )
    request: dict[str, Any] = {
        "kind": VALIDATION_REQUEST_KIND,
        "schema_version": VALIDATION_REQUEST_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "package": PLUGIN_NAME,
            "package_version": package_version(),
            "repo": repo.name,
            "git": git_state,
        },
        "request": {
            "scope": "explicit" if agents else scope,
            "base_ref": base_ref,
            "regenerated": regenerated,
            "publishable": publishable,
        },
        "generated_artifacts": generated_state,
        "agents": agent_entries,
        "warnings": sorted(dict.fromkeys(warnings)),
        "errors": errors,
        "recommended_next_steps": _recommended_next_steps(generated_state, errors),
    }

    output.expanduser().parent.mkdir(parents=True, exist_ok=True)
    output.expanduser().write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request


def validation_request_summary(request: dict[str, Any], *, output: Path) -> str:
    """Return a short Markdown-ish CLI summary for a validation request."""

    source = request["source"]
    git_state = source["git"]
    generated = request["generated_artifacts"]
    agents = ", ".join(agent["id"] for agent in request["agents"]) or "none"
    lines = [
        f"validation request: {output}",
        f"source: {source['package']} {source['package_version']} @ {git_state['commit']}",
        f"branch: {git_state['branch'] or '(detached)'}",
        f"scope: {request['request']['scope']}",
        f"agents: {agents}",
        f"publishable: {str(request['request']['publishable']).lower()}",
        f"generated artifacts: {'current' if generated['current'] else 'stale'}",
    ]
    if request["warnings"]:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in request["warnings"])
    if request["errors"]:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in request["errors"])
    if request["recommended_next_steps"]:
        lines.append("recommended next steps:")
        lines.extend(f"- {step}" for step in request["recommended_next_steps"])
    return "\n".join(lines)


def generated_artifact_state(repo_root: Path, *, all_recipe_paths: Sequence[Path]) -> dict[str, Any]:
    """Return whether checked-in generated artifacts match a temp publication."""

    with tempfile.TemporaryDirectory(prefix="endor-agent-kit-generated-") as temp:
        generated_root = Path(temp)
        publish_recipes(list(all_recipe_paths), generated_root, prune=True, include_plugins=True)
        changed = _changed_generated_paths(repo_root, generated_root)
    return {
        "current": not changed,
        "changed_paths": changed[:100],
        "changed_path_count": len(changed),
        "check": "temp publish comparison against generated catalog surfaces",
        "surfaces": list(_generated_surface_relatives(repo_root, generated_root)),
    }


def _selected_recipe_paths(
    repo: Path,
    *,
    agents: Sequence[str],
    scope: str,
    base_ref: str,
) -> list[Path]:
    if agents:
        return [_recipe_path_for_agent(repo, agent) for agent in dict.fromkeys(agents)]
    if scope in {"release-candidate", "all"}:
        return _all_recipe_paths(repo)
    if scope != "changed":
        raise ValueError(f"unsupported lifecycle scope: {scope}")
    changed_agent_ids = _changed_source_agent_ids(repo, base_ref)
    return [
        _recipe_path_for_agent(repo, agent_id)
        for agent_id in sorted(changed_agent_ids)
        if _recipe_path_for_agent(repo, agent_id).is_file()
    ]


def _all_recipe_paths(repo: Path) -> list[Path]:
    return sorted((repo / "source" / "agents").glob("*/recipe.yaml"))


def _recipe_path_for_agent(repo: Path, agent_id: str) -> Path:
    return repo / "source" / "agents" / agent_id / "recipe.yaml"


def _agent_entry(repo: Path, recipe_path: Path, *, base_ref: str) -> dict[str, Any]:
    relative_recipe = _relative(repo, recipe_path)
    errors = [f"{relative_recipe}: {error}" for error in validate_recipe_file(recipe_path)]
    warnings: list[str] = []
    new_agent = _recipe_is_new_at_base(repo, relative_recipe, base_ref)
    authoring = check_source_recipe_authoring(recipe_path, new_agent=new_agent)
    errors.extend(_authoring_issue_dict(repo, issue) for issue in authoring.errors)
    warnings.extend(_authoring_issue_dict(repo, issue) for issue in authoring.warnings)

    recipe: EndorAgentRecipe | None
    try:
        recipe = load_recipe(recipe_path)
    except Exception as exc:
        errors.append(f"{relative_recipe}: failed to load recipe: {exc}")
        recipe = None

    agent_id = recipe.id if recipe else recipe_path.parent.name
    workflow = load_knowledge_pack().workflow_for(agent_id)
    task_profiles = [profile.id for profile in workflow.task_profiles] if workflow else []
    if not task_profiles:
        warnings.append(f"{relative_recipe}: no source-derived task profiles found")

    structured_contract = None
    if agent_id in STRUCTURED_OUTPUT_CONTRACTS:
        structured_contract = {
            "id": agent_id,
            "required_fields": list(required_fields_for(agent_id)),
        }
    else:
        warnings.append(f"{relative_recipe}: no structured output contract found")

    profile_contracts = {
        profile.id: compile_profile_contract(
            agent_id,
            profile.id,
            knowledge_pack_root=repo / "source" / "endor-knowledge-pack",
        ).to_dict()
        for profile in (workflow.task_profiles if workflow else ())
        if agent_id in STRUCTURED_OUTPUT_CONTRACTS
    }
    evidence_plans = {
        plan.profile_id: plan.to_dict()
        for plan in compile_evidence_plans(
            agent_id,
            knowledge_pack_root=repo / "source" / "endor-knowledge-pack",
        )
    }

    compatible_hosts = list(recipe.compatible_hosts if recipe else ())
    generated_targets = _generated_targets_for_recipe(recipe)
    provider_targets = _provider_targets_for_recipe(recipe)
    return {
        "id": agent_id,
        "name": recipe.name if recipe else agent_id,
        "recipe": relative_recipe,
        "recipe_version": recipe.version if recipe else "",
        "new_agent": new_agent,
        "compatible_hosts": compatible_hosts,
        "generated_targets": generated_targets,
        "provider_targets": provider_targets,
        "task_profiles": task_profiles,
        "default_task_profile": default_task_profile_for_agent(agent_id),
        "structured_output_contract": structured_contract,
        "profile_contracts": profile_contracts,
        "evidence_plans": evidence_plans,
        "coverage": {
            "task_profiles": "present" if task_profiles else "missing",
            "structured_output_contract": "present" if structured_contract else "missing",
            "evidence_plans": "present" if evidence_plans else "not_declared",
        },
        "warnings": warnings,
        "errors": errors,
    }


def _generated_targets_for_recipe(recipe: EndorAgentRecipe | None) -> list[str]:
    if recipe is None:
        return []
    targets = set(recipe.compatible_hosts)
    if "claude-code" in recipe.compatible_hosts:
        targets.add("plugin:claude")
    if "codex" in recipe.compatible_hosts:
        targets.update({"plugin:codex", "cursor", "cursor-sdk"})
    if "gemini" in recipe.compatible_hosts:
        targets.update({"plugin:gemini", "plugin:antigravity"})
    return sorted(targets)


def _provider_targets_for_recipe(recipe: EndorAgentRecipe | None) -> list[str]:
    if recipe is None:
        return []
    targets = set()
    if "claude-code" in recipe.compatible_hosts:
        targets.add("claude")
    if "codex" in recipe.compatible_hosts:
        targets.update({"codex", "cursor"})
    if "gemini" in recipe.compatible_hosts:
        targets.update({"antigravity", "gemini"})
    return sorted(targets)


def _git_state(repo: Path, *, base_ref: str) -> dict[str, Any]:
    status = _git(repo, "status", "--porcelain", "--untracked-files=all", check=False).splitlines()
    remote_url = _git(repo, "remote", "get-url", "origin", check=False).strip()
    return {
        "branch": _git(repo, "branch", "--show-current", check=False).strip(),
        "commit": _git(repo, "rev-parse", "--short", "HEAD", check=False).strip(),
        "base_ref": base_ref,
        "remote_url": remote_url,
        "dirty": bool(status),
        "dirty_paths": status,
    }


def _changed_source_agent_ids(repo: Path, base_ref: str) -> set[str]:
    paths: set[str] = set()
    for command in (
        ("diff", "--name-only", f"{base_ref}...HEAD"),
        ("diff", "--name-only"),
        ("diff", "--name-only", "--cached"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(_git(repo, *command, check=False).splitlines())
    return {
        parts[2]
        for path in paths
        if (parts := Path(path).parts)
        and len(parts) >= 3
        and parts[0] == "source"
        and parts[1] == "agents"
    }


def _recipe_is_new_at_base(repo: Path, relative_recipe: str, base_ref: str) -> bool:
    return _run_git(repo, "cat-file", "-e", f"{base_ref}:{relative_recipe}").returncode != 0


def _changed_generated_paths(repo_root: Path, generated_root: Path) -> list[str]:
    changed: list[str] = []
    for relative in _generated_surface_relatives(repo_root, generated_root):
        repo_path = repo_root / relative
        generated_path = generated_root / relative
        if not repo_path.exists() or not generated_path.exists():
            changed.append(relative)
            continue
        if repo_path.is_file() or generated_path.is_file():
            if (
                not repo_path.is_file()
                or not generated_path.is_file()
                or repo_path.read_bytes() != generated_path.read_bytes()
            ):
                changed.append(relative)
            continue
        changed.extend(_changed_tree_paths(repo_path, generated_path, relative))
    return sorted(dict.fromkeys(changed))


def _generated_surface_relatives(repo_root: Path, generated_root: Path) -> tuple[str, ...]:
    root_skills = sorted(
        set(_generated_root_skill_names(repo_root))
        | set(_generated_root_skill_names(generated_root))
    )
    return tuple(GENERATED_SURFACES) + tuple(f"skills/{name}" for name in root_skills)


def _generated_root_skill_names(root: Path) -> tuple[str, ...]:
    skills = root / "skills"
    if not skills.is_dir():
        return ()
    return tuple(
        child.name
        for child in sorted(skills.iterdir())
        if child.is_dir() and child.name not in SOURCE_ONLY_ROOT_SKILLS
    )


def _changed_tree_paths(repo_path: Path, generated_path: Path, relative_root: str) -> list[str]:
    repo_files = _tree_files(repo_path)
    generated_files = _tree_files(generated_path)
    changed = []
    for relative in sorted(set(repo_files) | set(generated_files)):
        repo_file = repo_files.get(relative)
        generated_file = generated_files.get(relative)
        if repo_file is None or generated_file is None or repo_file.read_bytes() != generated_file.read_bytes():
            changed.append(f"{relative_root}/{relative}")
    return changed


def _tree_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not _ignored_generated_path(path)
    }


def _ignored_generated_path(path: Path) -> bool:
    return "__pycache__" in path.parts or path.name == ".DS_Store" or path.suffix == ".pyc"


def _recommended_next_steps(generated_state: dict[str, Any], errors: list[str]) -> list[str]:
    steps: list[str] = []
    if not generated_state["current"]:
        steps.append(
            "Run endor-agent-kit lifecycle prepare --scope <scope> "
            "--regenerate --output <tmp>/validation-request.json"
        )
    if errors:
        steps.append("Fix source validation errors before treating the request as publishable.")
    return steps


def _authoring_issue_dict(repo: Path, issue: Any) -> str:
    path = f" ({_relative(repo, issue.path)})" if issue.path else ""
    return f"{issue.code}: {issue.message}{path}"


def _relative(repo: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git(repo: Path, *args: str, check: bool = True) -> str:
    completed = _run_git(repo, *args)
    if check and completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
