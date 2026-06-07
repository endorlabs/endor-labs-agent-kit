"""Command line interface for Endor Agent Kit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from endor_agent_kit.compilers import (
    compile_claude_code,
    compile_claude_managed_agents,
    compile_codex,
    compile_gemini,
    compile_portable,
    compile_raw,
)
from endor_agent_kit.compilers.rendering import EDITION_CHOICES
from endor_agent_kit.endor_context import (
    DEFAULT_CONTEXT_PATH,
    refresh_endor_context,
    verify_endor_context,
)
from endor_agent_kit.guardrails import check_catalog_guardrails
from endor_agent_kit.install import (
    check_claude_code_install,
    check_claude_managed_agents_install,
    check_codex_install,
    check_portable_install,
)
from endor_agent_kit.portable_runtime_conformance import adapter_response_conformance_errors
from endor_agent_kit.provenance import build_provenance_statement, verify_catalog_provenance
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.recipe import load_yaml_file
from endor_agent_kit.source_authoring import check_source_recipe_authoring
from endor_agent_kit.structured_output_contracts import (
    json_schema_for_agent,
    known_structured_agent_ids,
)
from endor_agent_kit.workflow_output_contracts.commands import (
    add_workflow_command_parsers,
    run_workflow_command,
)
from endor_agent_kit.validator import validate_recipe_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="endor-agent-kit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a recipe")
    validate_parser.add_argument("recipe", type=Path)

    authoring_parser = subparsers.add_parser(
        "authoring-check",
        help="Check source-first authoring invariants for a recipe",
    )
    authoring_parser.add_argument("recipe", type=Path)
    authoring_parser.add_argument(
        "--new-agent",
        action="store_true",
        help="Require the stricter file set and eval coverage expected for new agents",
    )

    doctor_new_agent_parser = subparsers.add_parser(
        "doctor-new-agent",
        help="Run the contributor-facing pre-PR checks for a new source agent",
    )
    doctor_new_agent_parser.add_argument("recipe", type=Path)

    compile_parser = subparsers.add_parser("compile", help="Compile a recipe")
    compile_parser.add_argument("recipe", type=Path)
    compile_parser.add_argument(
        "--target",
        choices=("claude-code", "claude-managed-agents", "codex", "gemini", "portable", "raw"),
        required=True,
    )
    compile_parser.add_argument(
        "--edition",
        "--variant",
        dest="edition",
        choices=EDITION_CHOICES,
        default=None,
        help="Claude Code edition to compile; legacy standard/extended aliases are accepted",
    )

    publish_parser = subparsers.add_parser("publish", help="Publish customer-facing artifacts")
    publish_parser.add_argument("recipes", nargs="+", type=Path)
    publish_parser.add_argument("--dest", type=Path, required=True, help="Distribution repository path")
    publish_parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove previously published agents that are not in the recipe set",
    )
    publish_parser.add_argument(
        "--include-plugins",
        action="store_true",
        help="Also generate opt-in plugin packages from published host artifacts",
    )

    check_guardrails_parser = subparsers.add_parser(
        "check-guardrails",
        help="Check generated catalog artifacts against guardrail policies",
    )
    check_guardrails_parser.add_argument("--catalog-root", default=Path("."), type=Path)

    validate_adapter_response_parser = subparsers.add_parser(
        "validate-adapter-response",
        help="Check a portable runtime adapter response against the Portable Evidence Schema",
    )
    validate_adapter_response_parser.add_argument("response", type=Path)

    structured_output_schema_parser = subparsers.add_parser(
        "structured-output-schema",
        help="Print the provider-neutral JSON Schema for an agent final output",
    )
    structured_output_schema_parser.add_argument(
        "--agent",
        required=True,
        choices=known_structured_agent_ids(),
    )

    verify_provenance_parser = subparsers.add_parser(
        "verify-provenance",
        help="Verify generated catalog artifacts against the manifest checksums",
    )
    verify_provenance_parser.add_argument("--catalog-root", default=Path("."), type=Path)

    verify_endor_context_parser = subparsers.add_parser(
        "verify-endor-context",
        help="Verify committed Endor API/docs context provenance",
    )
    verify_endor_context_parser.add_argument(
        "--context-file",
        default=DEFAULT_CONTEXT_PATH,
        type=Path,
        help="Path to the Endor context provenance JSON",
    )
    verify_endor_context_parser.add_argument(
        "--upstream",
        action="store_true",
        help="Compare committed provenance with live Endor OpenAPI and docs",
    )

    refresh_endor_context_parser = subparsers.add_parser(
        "refresh-endor-context",
        help="Refresh committed Endor API/docs context provenance from upstream",
    )
    refresh_endor_context_parser.add_argument(
        "--context-file",
        default=DEFAULT_CONTEXT_PATH,
        type=Path,
        help="Path to write the Endor context provenance JSON",
    )
    refresh_endor_context_parser.add_argument(
        "--checked-at",
        help="ISO date to record in provenance; defaults to today's date",
    )

    provenance_statement_parser = subparsers.add_parser(
        "provenance-statement",
        help="Print the SLSA-style in-toto provenance statement for the catalog",
    )
    provenance_statement_parser.add_argument("--catalog-root", default=Path("."), type=Path)

    add_workflow_command_parsers(subparsers)

    check_install_parser = subparsers.add_parser(
        "check-install",
        help="Check whether an installed host artifact matches the catalog",
    )
    check_install_parser.add_argument("--agent", required=True)
    check_install_parser.add_argument(
        "--host",
        choices=("claude-code", "claude-managed-agents", "codex", "portable"),
        default="claude-code",
    )
    check_install_parser.add_argument("--repo", type=Path)
    check_install_parser.add_argument("--codex-home", type=Path)
    check_install_parser.add_argument("--managed-agent-dir", type=Path)
    check_install_parser.add_argument("--portable-dir", type=Path)
    check_install_parser.add_argument("--catalog-root", default=Path("."), type=Path)

    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_recipe_file(args.recipe)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.recipe}")
        return 0

    if args.command == "authoring-check":
        report = check_source_recipe_authoring(args.recipe, new_agent=args.new_agent)
        for warning in report.warnings:
            print(f"WARNING: {warning.code}: {warning.message}")
        if report.errors:
            for error in report.errors:
                print(f"ERROR: {error.code}: {error.message}")
            return 1
        print(f"OK: {args.recipe}")
        return 0

    if args.command == "doctor-new-agent":
        return _doctor_new_agent(args.recipe)

    if args.command == "compile":
        errors = validate_recipe_file(args.recipe)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        try:
            if args.target == "claude-code":
                outputs = compile_claude_code(args.recipe, edition=args.edition)
            elif args.target == "claude-managed-agents":
                outputs = compile_claude_managed_agents(args.recipe, edition=args.edition)
            elif args.target == "codex":
                if args.edition is not None:
                    print("ERROR: --edition/--variant is not valid for Codex skill artifacts")
                    return 1
                outputs = compile_codex(args.recipe)
            elif args.target == "gemini":
                if args.edition is not None:
                    print("ERROR: --edition/--variant is not valid for Gemini CLI artifacts")
                    return 1
                outputs = compile_gemini(args.recipe)
            elif args.target == "portable":
                if args.edition is not None:
                    print("ERROR: --edition/--variant is not valid for portable artifacts")
                    return 1
                outputs = compile_portable(args.recipe)
            else:
                if args.edition is not None:
                    print("ERROR: --edition/--variant is only valid for Claude provider targets")
                    return 1
                outputs = compile_raw(args.recipe)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        for output in outputs:
            print(output)
        return 0

    if args.command == "publish":
        try:
            outputs = publish_recipes(
                args.recipes,
                args.dest,
                prune=args.prune,
                include_plugins=args.include_plugins,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        for output in outputs:
            print(output)
        return 0

    if args.command == "check-guardrails":
        errors = check_catalog_guardrails(args.catalog_root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.catalog_root}")
        return 0

    if args.command == "validate-adapter-response":
        try:
            data = json.loads(args.response.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"ERROR: {exc}")
            return 1
        except json.JSONDecodeError as exc:
            print(f"ERROR: invalid JSON: {exc}")
            return 1
        if not isinstance(data, dict):
            print("ERROR: adapter response must be a JSON object")
            return 1
        errors = adapter_response_conformance_errors(data)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.response}")
        return 0

    if args.command == "structured-output-schema":
        print(json.dumps(json_schema_for_agent(args.agent), indent=2, sort_keys=True))
        return 0

    if args.command == "verify-provenance":
        errors = verify_catalog_provenance(args.catalog_root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.catalog_root}")
        return 0

    if args.command == "verify-endor-context":
        report = verify_endor_context(args.context_file, upstream=args.upstream)
        for warning in report.warnings:
            print(f"WARNING: {warning}")
        if report.errors:
            for error in report.errors:
                print(f"ERROR: {error}")
            return 1
        suffix = " against upstream" if args.upstream else ""
        print(f"OK: {args.context_file}{suffix}")
        return 0

    if args.command == "refresh-endor-context":
        try:
            payload = refresh_endor_context(
                args.context_file,
                checked_at=args.checked_at,
            )
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print(
            "OK: refreshed "
            f"{args.context_file} "
            f"(OpenAPI {payload['openapi']['sha256']}, checked_at {payload['checked_at']})"
        )
        return 0

    if args.command == "provenance-statement":
        try:
            statement = build_provenance_statement(args.catalog_root)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print(json.dumps(statement, indent=2, sort_keys=True))
        return 0

    workflow_result = run_workflow_command(args)
    if workflow_result is not None:
        return workflow_result

    if args.command == "check-install":
        if args.host == "codex":
            codex_home = args.codex_home or Path.home() / ".codex"
            errors = check_codex_install(
                args.agent,
                codex_home,
                catalog_root=args.catalog_root,
            )
            install_path = codex_home / "skills" / args.agent / "SKILL.md"
        elif args.host == "portable":
            if args.portable_dir is None:
                print("ERROR: --portable-dir is required for --host portable")
                return 1
            errors = check_portable_install(
                args.agent,
                args.portable_dir,
                catalog_root=args.catalog_root,
            )
            install_path = args.portable_dir
        elif args.host == "claude-managed-agents":
            managed_agent_dir = (
                args.managed_agent_dir
                or args.catalog_root / "claude-managed-agents" / args.agent
            )
            errors = check_claude_managed_agents_install(
                args.agent,
                managed_agent_dir,
                catalog_root=args.catalog_root,
            )
            install_path = managed_agent_dir
        else:
            if args.repo is None:
                print("ERROR: --repo is required for --host claude-code")
                return 1
            errors = check_claude_code_install(
                args.agent,
                args.repo,
                catalog_root=args.catalog_root,
            )
            install_path = args.repo / ".claude" / "agents" / f"{args.agent}.md"
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {install_path}")
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


def _doctor_new_agent(recipe_path: Path) -> int:
    """Print a contributor-facing health report for a new source agent."""

    report = check_source_recipe_authoring(recipe_path, new_agent=True)
    recipe_errors = [error for error in report.errors if error.code == "recipe.validation"]
    authoring_errors = [error for error in report.errors if error.code != "recipe.validation"]

    print(f"Doctor New Agent: {recipe_path}")
    _print_doctor_check("recipe validation", not recipe_errors)
    _print_doctor_check("strict new-agent authoring", not authoring_errors)

    for warning in report.warnings:
        print(f"WARNING: {warning.code}: {warning.message}{_issue_location(warning)}")
    for error in report.errors:
        print(f"ERROR: {error.code}: {error.message}{_issue_location(error)}")

    data = _load_recipe_data_for_doctor(recipe_path)
    source_dir = report.source_dir
    agent_id = report.agent_id or "<unknown>"
    evals_path = source_dir / str(data.get("evals") or "evals/cases.yaml")
    eval_case_count = _eval_case_count(evals_path)
    hosts = _string_list(data.get("compatible_hosts"))
    safety_class = str(data.get("safety_class") or "unknown")

    print("")
    print("Source summary:")
    print(f"- agent id: {agent_id}")
    print(f"- source dir: {source_dir}")
    print(f"- safety class: {safety_class}")
    print(f"- compatible hosts: {', '.join(hosts) if hosts else '<none>'}")
    print(f"- eval cases: {eval_case_count if eval_case_count is not None else '<unreadable>'}")
    print(f"- architecture: {source_dir / 'architecture.svg'}")

    print("")
    print("Next commands:")
    print("endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins")
    print("endor-agent-kit check-guardrails --catalog-root .")
    print("endor-agent-kit verify-provenance --catalog-root .")
    print("python -m pytest -q")
    print(
        "git diff --exit-code -- README.md manifest.json .agents/plugins .claude-plugin "
        ".cursor-plugin agents assets claude-code claude-managed-agents codex cursor-sdk "
        "gemini plugins portable skills"
    )

    if report.errors:
        return 1
    print("")
    print("OK: new agent is ready for an Agent Kit PR after regenerated artifacts are committed.")
    return 0


def _print_doctor_check(label: str, ok: bool) -> None:
    prefix = "OK" if ok else "FAIL"
    print(f"{prefix}: {label}")


def _issue_location(issue: object) -> str:
    path = getattr(issue, "path", None)
    return f" ({path})" if path else ""


def _load_recipe_data_for_doctor(recipe_path: Path) -> dict[str, object]:
    try:
        data = load_yaml_file(recipe_path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _eval_case_count(evals_path: Path) -> int | None:
    try:
        data = load_yaml_file(evals_path)
    except Exception:
        return None
    cases = data.get("cases") if isinstance(data, dict) else None
    return len(cases) if isinstance(cases, list) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


if __name__ == "__main__":
    raise SystemExit(main())
