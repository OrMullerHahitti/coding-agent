"""Reviewer worker agent factory.

Creates a worker specialized for code review and quality analysis.
"""

from ...clients.base import BaseLLMClient
from ...tools.filesystem import ListDirectoryTool, ReadFileTool
from ...tools.system import RunCommandTool
from ..prompts import REVIEWER_PROMPT
from ..worker import WorkerAgent


def create_reviewer_worker(
    client: BaseLLMClient,
    allow_lint_commands: bool = True,
) -> WorkerAgent:
    """Create a reviewer worker agent.

    The reviewer worker is specialized for code review, quality analysis,
    and checking adherence to coding standards. It has read-only file access
    and can optionally run linting commands.

    Args:
        client: LLM client for the worker.
        allow_lint_commands: Whether to allow running lint/check commands.

    Returns:
        Configured reviewer WorkerAgent.
    """
    tools = [
        ReadFileTool(),
        ListDirectoryTool(),
    ]

    if allow_lint_commands:
        tools.append(RunCommandTool())

    return WorkerAgent(
        name="reviewer",
        client=client,
        tools=tools,
        system_prompt=REVIEWER_PROMPT,
        description=(
            "Code reviewer for quality, security, and best practices analysis. "
            "Has read-only access to files and can run lint commands."
        ),
    )
