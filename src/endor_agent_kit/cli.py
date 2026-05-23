"""Command line interface for Endor Agent Kit."""

from __future__ import annotations

import argparse
from pathlib import Path

from endor_agent_kit.compilers import (
    compile_claude_code,
    compile_claude_managed_agents,
    compile_raw,
)
from endor_agent_kit.compilers.claude_code import EDITION_CHOICES
from endor_agent_kit.install import check_claude_code_install
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.sca_remediation import (
    lint_sca_pr_body,
    load_json_payload,
    render_sca_pr_body,
    validate_sca_gate_payload,
)
from endor_agent_kit.validator import validate_recipe_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="endor-agent-kit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a recipe")
    validate_parser.add_argument("recipe", type=Path)

    compile_parser = subparsers.add_parser("compile", help="Compile a recipe")
    compile_parser.add_argument("recipe", type=Path)
    compile_parser.add_argument(
        "--target",
        choices=("claude-code", "claude-managed-agents", "raw"),
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

    validate_output_parser = subparsers.add_parser(
        "validate-sca-output",
        help="Validate structured sca-remediation-agent output for a workflow gate",
    )
    validate_output_parser.add_argument("payload", type=Path)
    validate_output_parser.add_argument(
        "--gate",
        choices=("selection-plan", "apply", "validate", "pr"),
        default="selection-plan",
    )

    render_pr_parser = subparsers.add_parser(
        "render-sca-pr-body",
        help="Render an AURI-style SCA remediation PR body from normalized JSON",
    )
    render_pr_parser.add_argument("payload", type=Path)

    lint_pr_parser = subparsers.add_parser(
        "lint-sca-pr-body",
        help="Lint an AURI-style SCA remediation PR body",
    )
    lint_pr_parser.add_argument("body", type=Path)

    check_install_parser = subparsers.add_parser(
        "check-install",
        help="Check whether a repo-level Claude Code agent install matches the catalog",
    )
    check_install_parser.add_argument("--agent", required=True)
    check_install_parser.add_argument("--repo", required=True, type=Path)
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

    if args.command == "validate-sca-output":
        try:
            payload = load_json_payload(args.payload)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        errors = validate_sca_gate_payload(payload, gate=args.gate)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.payload}")
        return 0

    if args.command == "render-sca-pr-body":
        try:
            payload = load_json_payload(args.payload)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print(render_sca_pr_body(payload), end="")
        return 0

    if args.command == "lint-sca-pr-body":
        try:
            body = args.body.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: {exc}")
            return 1
        errors = lint_sca_pr_body(body)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.body}")
        return 0

    if args.command == "check-install":
        errors = check_claude_code_install(
            args.agent,
            args.repo,
            catalog_root=args.catalog_root,
        )
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        install_path = args.repo / ".claude" / "agents" / f"{args.agent}.md"
        print(f"OK: {install_path}")
        return 0

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
