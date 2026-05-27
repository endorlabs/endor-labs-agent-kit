"""Command line interface for Endor Agent Kit."""

from __future__ import annotations

import argparse
from pathlib import Path

from endor_agent_kit.compilers import (
    compile_claude_code,
    compile_claude_managed_agents,
    compile_codex,
    compile_portable,
    compile_raw,
)
from endor_agent_kit.compilers.rendering import EDITION_CHOICES
from endor_agent_kit.install import (
    check_claude_code_install,
    check_claude_managed_agents_install,
    check_codex_install,
    check_portable_install,
)
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.source_authoring import check_source_recipe_authoring
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

    compile_parser = subparsers.add_parser("compile", help="Compile a recipe")
    compile_parser.add_argument("recipe", type=Path)
    compile_parser.add_argument(
        "--target",
        choices=("claude-code", "claude-managed-agents", "codex", "portable", "raw"),
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
            outputs = publish_recipes(args.recipes, args.dest, prune=args.prune)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        for output in outputs:
            print(output)
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


if __name__ == "__main__":
    raise SystemExit(main())
