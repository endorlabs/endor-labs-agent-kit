"""Compiler targets for Endor Agent Kit recipes."""

from endor_agent_kit.compilers.claude_code import compile_claude_code
from endor_agent_kit.compilers.claude_managed_agents import compile_claude_managed_agents
from endor_agent_kit.compilers.github_copilot_plugin import compile_github_copilot_plugin
from endor_agent_kit.compilers.raw import compile_raw

__all__ = [
    "compile_claude_code",
    "compile_claude_managed_agents",
    "compile_github_copilot_plugin",
    "compile_raw",
]
