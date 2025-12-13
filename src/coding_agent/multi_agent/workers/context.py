"""Context worker agent factory.

Creates a worker specialized for exploring and understanding codebases.
"""

from ...clients.base import BaseLLMClient
from ...tools.filesystem import ListDirectoryTool, ReadFileTool
from ...tools.system import RunCommandTool
from ..prompts import CONTEXT_PROMPT
from ..worker import WorkerAgent


def create_context_worker(
    client: BaseLLMClient,
    allow_commands: bool = True,
) -> WorkerAgent:
    """Create a context worker agent.

    The context worker is specialized for exploring project structure,
    reading configuration files, and understanding codebase architecture.
    It has read-only file access and can optionally run exploration commands.

    Args:
        client: LLM client for the worker.
        allow_commands: Whether to allow running commands like tree, git log, etc.

    Returns:
        Configured context WorkerAgent.
    """
    tools = [
        ReadFileTool(),
        ListDirectoryTool(),
    ]

    if allow_commands:
        tools.append(RunCommandTool())

    return WorkerAgent(
        name="context",
        client=client,
        tools=tools,
        system_prompt=CONTEXT_PROMPT,
        description=(
            "Codebase analyst for exploring project structure, dependencies, "
            "and architecture. Has read-only file access and can run exploration commands."
        ),
    )
