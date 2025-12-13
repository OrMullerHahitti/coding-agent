"""Tool execution logic for the agent.

This module handles the execution of tool calls, including
confirmation checking and interrupt handling.
"""

import fnmatch
from typing import TYPE_CHECKING

from ..exceptions import ConfirmationRequested, InterruptRequested
from ..tools.base import BaseTool
from ..types import ToolCall

if TYPE_CHECKING:
    from .memory_manager import MemoryManager


class ToolExecutor:
    """Handles tool execution with confirmation and interrupt patterns.

    This class manages the execution of tool calls, including:
    - Auto-approval pattern matching
    - Confirmation requirement checking
    - Interrupt handling for human-in-the-loop tools
    """

    def __init__(
        self,
        tools: dict[str, BaseTool],
        auto_approve_patterns: dict[str, list[str]] | None = None,
    ):
        """Initialize the tool executor.

        Args:
            tools: Dictionary mapping tool names to tool instances.
            auto_approve_patterns: Dict mapping operation types to patterns
                to auto-approve. Example: {"write": ["tests/*", "*.log"]}
        """
        self.tools = tools
        self.auto_approve_patterns = auto_approve_patterns or {}

    def is_auto_approved(self, operation: str, value: str) -> bool:
        """Check if an operation is auto-approved by configured patterns.

        Args:
            operation: The operation type (e.g., "write", "execute").
            value: The value to check against patterns.

        Returns:
            True if the operation matches an auto-approve pattern.
        """
        patterns = self.auto_approve_patterns.get(operation, [])
        return any(fnmatch.fnmatch(value, p) for p in patterns)

    def execute_single_tool(
        self,
        tool: BaseTool,
        tool_call_id: str,
        arguments: dict,
        verbose: bool = False,
    ) -> str:
        """Execute a single tool and return the result.

        Args:
            tool: The tool to execute.
            tool_call_id: The ID of the tool call.
            arguments: The arguments to pass to the tool.
            verbose: Whether to print verbose output.

        Returns:
            The tool execution result as a string.

        Raises:
            InterruptRequested: If the tool requires user input.
        """
        if getattr(tool, "INTERRUPT_TOOL", False):
            result = tool.execute(**arguments, _tool_call_id=tool_call_id)
        else:
            result = tool.execute(**arguments)

        if verbose:
            print(f"  Result: {result}")

        return str(result)

    def check_confirmation_required(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ConfirmationRequested | None:
        """Check if a tool call requires confirmation.

        Args:
            tool: The tool being called.
            tool_call: The tool call to check.

        Returns:
            ConfirmationRequested exception if confirmation is needed, None otherwise.
        """
        if not getattr(tool, "REQUIRES_CONFIRMATION", False):
            return None

        op_type = getattr(tool, "OPERATION_TYPE", "")
        check_arg = getattr(tool, "CONFIRMATION_CHECK_ARG", "path")
        check_value = tool_call.arguments.get(check_arg, "")

        if self.is_auto_approved(op_type, check_value):
            return None

        return ConfirmationRequested(
            tool_name=tool_call.name,
            tool_call_id=tool_call.id,
            message=tool.get_confirmation_message(**tool_call.arguments),
            operation=op_type,
            arguments=tool_call.arguments,
        )

    def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        memory: "MemoryManager",
        verbose: bool = False,
    ) -> None:
        """Execute multiple tool calls and add results to memory.

        Args:
            tool_calls: List of tool calls to execute.
            memory: The memory manager to store results.
            verbose: Whether to print verbose output.

        Raises:
            InterruptRequested: If a tool requests user input.
            ConfirmationRequested: If a tool requires confirmation.
        """
        for tool_call in tool_calls:
            tool_name = tool_call.name

            # handle unknown tool
            if tool_name not in self.tools:
                error_msg = f"Tool '{tool_name}' not found"
                print(f"Error: {error_msg}")
                memory.add_tool_result(tool_call.id, tool_name, error_msg)
                continue

            tool = self.tools[tool_name]

            # check if confirmation is required
            conf_request = self.check_confirmation_required(tool, tool_call)
            if conf_request:
                raise conf_request

            # log execution
            if verbose:
                print(f"[Verbose] Executing tool '{tool_name}' (ID: {tool_call.id})")
                print(f"  Args: {tool_call.arguments}")
            else:
                print(f"Executing tool: {tool_name} with args: {tool_call.arguments}")

            # execute the tool
            try:
                result = self.execute_single_tool(
                    tool, tool_call.id, tool_call.arguments, verbose
                )
                memory.add_tool_result(tool_call.id, tool_name, result)
            except (InterruptRequested, ConfirmationRequested):
                raise
            except Exception as e:
                error_msg = f"Tool execution failed: {e}"
                print(f"Error: {error_msg}")
                memory.add_tool_result(tool_call.id, tool_name, error_msg)

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: The tool name.

        Returns:
            The tool instance or None if not found.
        """
        return self.tools.get(name)

    def has_tool(self, name: str) -> bool:
        """Check if a tool exists.

        Args:
            name: The tool name.

        Returns:
            True if the tool exists.
        """
        return name in self.tools
