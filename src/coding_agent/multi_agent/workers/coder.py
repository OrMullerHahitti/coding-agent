"""Coder worker agent factory.

Creates a worker specialized for writing and modifying code.
"""

from ...clients.base import BaseLLMClient
from ...tools.calculator import CalculatorTool
from ...tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
from ...tools.python_repl import PythonREPLTool
from ...tools.system import RunCommandTool
from ..prompts import CODER_PROMPT
from ..worker import WorkerAgent


def create_coder_worker(
    client: BaseLLMClient,
    include_dangerous_tools: bool = True,
) -> WorkerAgent:
    """Create a coder worker agent.

    The coder worker is specialized for writing, reading, and modifying code.
    It has access to file system tools and code execution capabilities.

    Args:
        client: LLM client for the worker (coding-optimized model recommended).
        include_dangerous_tools: Whether to include tools that can modify files
            and execute code. Set to False for read-only mode.

    Returns:
        Configured coder WorkerAgent.
    """
    tools = [
        ReadFileTool(),
        ListDirectoryTool(),
        CalculatorTool(),
    ]

    if include_dangerous_tools:
        tools.extend([
            WriteFileTool(),
            RunCommandTool(),
            PythonREPLTool(),
        ])

    return WorkerAgent(
        name="coder",
        client=client,
        tools=tools,
        system_prompt=CODER_PROMPT,
        description=(
            "Senior software engineer for writing, reading, and modifying code. "
            "Has access to file system and code execution tools."
        ),
    )
