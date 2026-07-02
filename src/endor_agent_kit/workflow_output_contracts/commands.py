"""CLI command registry for Workflow Output Contract operations."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from endor_agent_kit.policy_pack import (
    load_policy_pack,
    policy_output_errors,
    policy_pack_sha256,
    validate_policy_pack_data,
)
from endor_agent_kit.workflow_output_contracts.ai_sast import (
    lint_ai_sast_approval_comment,
    lint_ai_sast_exception_policy_comment,
    lint_ai_sast_pr_body,
    load_json_payload as load_ai_sast_json_payload,
    render_ai_sast_approval_comment,
    render_ai_sast_exception_policy_comment,
    render_ai_sast_pr_body,
    validate_ai_sast_gate_payload,
)
from endor_agent_kit.workflow_output_contracts.cicd_posture import (
    load_json_payload as load_cicd_posture_json_payload,
    validate_cicd_posture_payload,
)
from endor_agent_kit.workflow_output_contracts.sca import (
    lint_sca_pr_body,
    load_json_payload as load_sca_json_payload,
    render_sca_pr_body,
    validate_sca_gate_payload,
)

Operation = Literal["validate", "render", "lint"]
PayloadLoader = Callable[[Path], dict[str, Any]]
Validator = Callable[[dict[str, Any]], list[str]]
GateValidator = Callable[..., list[str]]
Renderer = Callable[[dict[str, Any]], str]
Linter = Callable[[str], list[str]]


@dataclass(frozen=True)
class WorkflowCommand:
    """One CLI operation exposed by a Workflow Output Contract."""

    name: str
    help: str
    operation: Operation
    payload_loader: PayloadLoader | None = None
    renderer: Renderer | None = None
    linter: Linter | None = None
    validator: GateValidator | None = None
    gate_choices: tuple[str, ...] = ()
    default_gate: str = ""
    agent_id: str = ""
    mutating_gates: tuple[str, ...] = ()

    def add_parser(self, subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Register this command on an argparse subparser collection."""

        parser = subparsers.add_parser(self.name, help=self.help)
        if self.operation in {"validate", "render"}:
            parser.add_argument("payload", type=Path)
        else:
            parser.add_argument("body", type=Path)
        if self.operation == "validate":
            parser.add_argument("--gate", choices=self.gate_choices, default=self.default_gate)
            parser.add_argument(
                "--policy-pack",
                type=Path,
                help="Validate policy_context and policy_evaluations against a policy pack",
            )

    def run(self, args: argparse.Namespace) -> int:
        """Run this Workflow Output Contract command."""

        if self.operation == "lint":
            return self._run_lint(args)
        try:
            if self.payload_loader is None:
                raise ValueError(f"{self.name}: missing payload loader")
            payload = self.payload_loader(args.payload)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        if self.operation == "validate":
            return self._run_validate(args, payload)
        return self._run_render(payload)

    def _run_validate(self, args: argparse.Namespace, payload: dict[str, Any]) -> int:
        if self.validator is None:
            print(f"ERROR: {self.name}: missing validator")
            return 1
        errors = self.validator(payload, gate=args.gate)
        policy_pack_path = getattr(args, "policy_pack", None)
        if policy_pack_path:
            try:
                policy_pack = load_policy_pack(policy_pack_path)
                pack_errors = validate_policy_pack_data(policy_pack)
                if pack_errors:
                    errors.extend(f"policy_pack: {error}" for error in pack_errors)
                else:
                    errors.extend(
                        policy_output_errors(
                            payload,
                            policy_pack=policy_pack,
                            policy_sha256=policy_pack_sha256(policy_pack_path),
                            mutation_gate=args.gate in self.mutating_gates,
                        )
                    )
            except (OSError, ValueError) as exc:
                errors.append(f"policy_pack: {exc}")
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.payload}")
        return 0

    def _run_render(self, payload: dict[str, Any]) -> int:
        if self.renderer is None:
            print(f"ERROR: {self.name}: missing renderer")
            return 1
        print(self.renderer(payload), end="")
        return 0

    def _run_lint(self, args: argparse.Namespace) -> int:
        if self.linter is None:
            print(f"ERROR: {self.name}: missing linter")
            return 1
        try:
            body = args.body.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: {exc}")
            return 1
        errors = self.linter(body)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"OK: {args.body}")
        return 0


WORKFLOW_COMMANDS: tuple[WorkflowCommand, ...] = (
    WorkflowCommand(
        name="validate-sca-output",
        help="Validate structured sca-remediation output for a workflow gate",
        operation="validate",
        payload_loader=load_sca_json_payload,
        validator=validate_sca_gate_payload,
        gate_choices=("selection-plan", "apply", "validate", "pr"),
        default_gate="selection-plan",
        agent_id="sca-remediation",
        mutating_gates=("apply", "validate", "pr"),
    ),
    WorkflowCommand(
        name="render-sca-pr-body",
        help="Render an AURI-style SCA remediation PR body from normalized JSON",
        operation="render",
        payload_loader=load_sca_json_payload,
        renderer=render_sca_pr_body,
    ),
    WorkflowCommand(
        name="lint-sca-pr-body",
        help="Lint an AURI-style SCA remediation PR body",
        operation="lint",
        linter=lint_sca_pr_body,
    ),
    WorkflowCommand(
        name="validate-cicd-posture-output",
        help="Validate structured cicd-posture output and deterministic scores",
        operation="validate",
        payload_loader=load_cicd_posture_json_payload,
        validator=validate_cicd_posture_payload,
        gate_choices=("posture",),
        default_gate="posture",
        agent_id="cicd-posture",
    ),
    WorkflowCommand(
        name="validate-ai-sast-output",
        help="Validate structured ai-sast-triage output for a workflow gate",
        operation="validate",
        payload_loader=load_ai_sast_json_payload,
        validator=validate_ai_sast_gate_payload,
        gate_choices=("triage", "remediation", "pr", "exception"),
        default_gate="triage",
        agent_id="ai-sast-triage",
        mutating_gates=("remediation", "pr", "exception"),
    ),
    WorkflowCommand(
        name="render-ai-sast-pr-body",
        help="Render an AURI-style AI SAST remediation PR/MR body from normalized JSON",
        operation="render",
        payload_loader=load_ai_sast_json_payload,
        renderer=render_ai_sast_pr_body,
    ),
    WorkflowCommand(
        name="lint-ai-sast-pr-body",
        help="Lint an AURI-style AI SAST remediation PR/MR body",
        operation="lint",
        linter=lint_ai_sast_pr_body,
    ),
    WorkflowCommand(
        name="render-ai-sast-approval-comment",
        help="Render an AI SAST AppSec approval request comment from normalized JSON",
        operation="render",
        payload_loader=load_ai_sast_json_payload,
        renderer=render_ai_sast_approval_comment,
    ),
    WorkflowCommand(
        name="lint-ai-sast-approval-comment",
        help="Lint an AI SAST AppSec approval request comment",
        operation="lint",
        linter=lint_ai_sast_approval_comment,
    ),
    WorkflowCommand(
        name="render-ai-sast-exception-policy-comment",
        help="Render an AI SAST Endor exception policy decision comment from normalized JSON",
        operation="render",
        payload_loader=load_ai_sast_json_payload,
        renderer=render_ai_sast_exception_policy_comment,
    ),
    WorkflowCommand(
        name="lint-ai-sast-exception-policy-comment",
        help="Lint an AI SAST Endor exception policy decision comment",
        operation="lint",
        linter=lint_ai_sast_exception_policy_comment,
    ),
)
WORKFLOW_COMMAND_BY_NAME = {command.name: command for command in WORKFLOW_COMMANDS}


def add_workflow_command_parsers(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register Workflow Output Contract commands on the CLI parser."""

    for command in WORKFLOW_COMMANDS:
        command.add_parser(subparsers)


def run_workflow_command(args: argparse.Namespace) -> int | None:
    """Run a registry-backed Workflow Output Contract command, if matched."""

    command = WORKFLOW_COMMAND_BY_NAME.get(args.command)
    if command is None:
        return None
    return command.run(args)
