"""Tool implementations for the coding agent.

All tools inherit from BaseTool and implement the execute method.
"""

from .ask_user import AskUserTool
from .base import BaseTool
from .calculator import CalculatorTool
from .filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
from .python_repl import PythonREPLTool
from .search import TavilySearchTool
from .security import PathValidator
from .system import RunCommandTool

__all__ = [
    "BaseTool",
    "AskUserTool",
    "CalculatorTool",
    "ListDirectoryTool",
    "ReadFileTool",
    "WriteFileTool",
    "PythonREPLTool",
    "TavilySearchTool",
    "RunCommandTool",
    "PathValidator",
    "get_default_tools",
]


def get_default_tools() -> list[BaseTool]:
    """Get the default set of tools for the agent."""
    return [
        CalculatorTool(),
        ListDirectoryTool(),
        ReadFileTool(),
        WriteFileTool(),
        RunCommandTool(),
        PythonREPLTool(),
        TavilySearchTool(),
        AskUserTool(),
    ]
