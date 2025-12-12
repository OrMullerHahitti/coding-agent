"""Main agent implementation.

The CodingAgent orchestrates conversations between the user, LLM, and tools.
It uses unified types for all interactions, making it provider-agnostic.
"""

import fnmatch
from typing import Iterator

from .clients.base import BaseLLMClient
from .exceptions import ConfirmationRequested, InterruptRequested
from .stream_handler import StreamHandler
from .tools.base import BaseTool
from .types import (
    AgentRunResult,
    AgentState,
    ConfirmationInfo,
    InterruptInfo,
    MessageRole,
    ToolCall,
    UnifiedMessage,
    UnifiedResponse,
)


class CodingAgent:
    """Agent that coordinates between LLM and tools.

    The agent maintains conversation history and handles the tool-use loop:
    1. Send messages to LLM
    2. If LLM requests tool calls, execute them
    3. Add tool results to history
    4. Repeat until LLM produces a final response

    Supports interrupt pattern for human-in-the-loop tools like ask_user.
    Supports confirmation pattern for dangerous operations (file writes, commands, code execution).
    """

    def __init__(
        self,
        client: BaseLLMClient,
        tools: list[BaseTool],
        system_prompt: str = "You are a helpful coding assistant.",
        auto_approve_patterns: dict[str, list[str]] | None = None,
    ):
        """Initialize the agent.

        Args:
            client: The LLM client to use (provider-agnostic)
            tools: List of tools available to the LLM
            system_prompt: System prompt for the conversation
            auto_approve_patterns: Dict mapping operation types to patterns to auto-approve.
                Example: {"write": ["tests/*", "*.log"], "execute": ["ls", "pwd"]}
        """
        self.client = client
        self.tools = {tool.name: tool for tool in tools}
        self.tool_list = tools
        self.auto_approve_patterns = auto_approve_patterns or {}

        formatted_prompt = self.client.format_system_prompt(system_prompt, tools)
        self.history: list[UnifiedMessage] = [
            UnifiedMessage(role=MessageRole.SYSTEM, content=formatted_prompt)
        ]

        # state for interrupt handling
        self._pending_interrupt: InterruptInfo | None = None
        self._pending_tool_calls: list[ToolCall] | None = None

        # state for confirmation handling
        self._pending_confirmation: ConfirmationInfo | None = None

    def run(
        self,
        user_input: str,
        stream: bool = False,
        verbose: bool = False,
    ) -> AgentRunResult:
        """Run a conversation turn with the given user input.

        Args:
            user_input: The user's message
            stream: Whether to stream the response
            verbose: Whether to print verbose output

        Returns:
            AgentRunResult with state, content, or interrupt info
        """
        self.history.append(
            UnifiedMessage(role=MessageRole.USER, content=user_input)
        )

        return self._run_loop(stream=stream, verbose=verbose)

    def resume(
        self,
        tool_call_id: str,
        user_response: str,
        stream: bool = False,
        verbose: bool = False,
    ) -> AgentRunResult:
        """Resume agent execution after an interrupt.

        Args:
            tool_call_id: ID of the interrupted tool call
            user_response: User's response to the question
            stream: Whether to stream the response
            verbose: Whether to print verbose output

        Returns:
            AgentRunResult - may be completed or another interrupt

        Raises:
            ValueError: If no pending interrupt or ID mismatch
        """
        if not self._pending_interrupt:
            raise ValueError("No pending interrupt to resume")

        if self._pending_interrupt.tool_call_id != tool_call_id:
            raise ValueError(
                f"Tool call ID mismatch: expected {self._pending_interrupt.tool_call_id}, "
                f"got {tool_call_id}"
            )

        # add the user's response as a tool result
        self.history.append(UnifiedMessage(
            role=MessageRole.TOOL,
            content=user_response,
            tool_call_id=tool_call_id,
            name=self._pending_interrupt.tool_name,
        ))

        # process remaining tool calls if any
        remaining_calls = self._pending_tool_calls or []
        self._pending_interrupt = None
        self._pending_tool_calls = None

        if remaining_calls:
            try:
                self._execute_tool_calls(remaining_calls, verbose=verbose)
            except InterruptRequested as e:
                return self._create_interrupt_result(e, remaining_calls)

        # continue the agent loop
        return self._run_loop(stream=stream, verbose=verbose)

    def resume_confirmation(
        self,
        tool_call_id: str,
        confirmed: bool,
        stream: bool = False,
        verbose: bool = False,
    ) -> AgentRunResult:
        """Resume agent execution after a confirmation request.

        Args:
            tool_call_id: ID of the tool call awaiting confirmation
            confirmed: Whether the user confirmed the operation
            stream: Whether to stream the response
            verbose: Whether to print verbose output

        Returns:
            AgentRunResult - may be completed or another interrupt/confirmation

        Raises:
            ValueError: If no pending confirmation or ID mismatch
        """
        if not self._pending_confirmation:
            raise ValueError("No pending confirmation to resume")

        if self._pending_confirmation.tool_call_id != tool_call_id:
            raise ValueError(
                f"Tool call ID mismatch: expected {self._pending_confirmation.tool_call_id}, "
                f"got {tool_call_id}"
            )

        tool_name = self._pending_confirmation.tool_name
        arguments = self._pending_confirmation.arguments
        remaining_calls = self._pending_tool_calls or []
        self._pending_confirmation = None

        if confirmed:
            tool = self.tools[tool_name]
            try:
                result = self._execute_single_tool(tool, tool_call_id, arguments, verbose)
                self._add_tool_result(tool_call_id, tool_name, result)
            except InterruptRequested as e:
                self._pending_tool_calls = remaining_calls if remaining_calls else None
                return self._create_interrupt_result(e, [])
            except Exception as e:
                error_msg = f"Tool execution failed: {e}"
                print(f"Error: {error_msg}")
                self._add_tool_result(tool_call_id, tool_name, error_msg)
        else:
            self._add_tool_result(
                tool_call_id, tool_name,
                f"Operation cancelled by user: {tool_name} was not executed."
            )

        self._pending_tool_calls = None

        # process remaining tool calls if any
        if remaining_calls:
            try:
                self._execute_tool_calls(remaining_calls, verbose=verbose)
            except InterruptRequested as e:
                return self._create_interrupt_result(e, remaining_calls)
            except ConfirmationRequested as e:
                return self._create_confirmation_result(e, remaining_calls)

        # continue the agent loop
        return self._run_loop(stream=stream, verbose=verbose)

    def _run_loop(
        self,
        stream: bool = False,
        verbose: bool = False,
    ) -> AgentRunResult:
        """Internal agent loop that handles interrupts."""
        while True:
            response = self.client.generate(
                messages=self.history,
                tools=self.tool_list if self.tools else None,
                stream=stream,
            )

            # get the message from either streaming or non-streaming response
            if stream:
                assert isinstance(response, Iterator)
                handler = StreamHandler(verbose=verbose)
                message = handler.process_stream(response)
            else:
                assert isinstance(response, UnifiedResponse)
                message = response.message
                # print output for non-streaming (streaming prints during process)
                self._print_response(message, verbose)

            self.history.append(message)

            # handle tool calls or return completed result
            result = self._process_message(message, verbose)
            if result is not None:
                return result

    def _print_response(self, message: UnifiedMessage, verbose: bool) -> None:
        """Print response content for non-streaming mode.

        Args:
            message: The message to print.
            verbose: Whether to print reasoning content.
        """
        if verbose and message.reasoning_content:
            print(f"\n[Reasoning]: {message.reasoning_content}")
        if message.content:
            print(f"Agent: {message.content}")

    def _process_message(
        self,
        message: UnifiedMessage,
        verbose: bool,
    ) -> AgentRunResult | None:
        """Process a message, executing tool calls or returning completion.

        Args:
            message: The message to process.
            verbose: Whether to print verbose output.

        Returns:
            AgentRunResult if complete or interrupted, None if loop should continue.
        """
        if message.tool_calls:
            try:
                self._execute_tool_calls(message.tool_calls, verbose=verbose)
            except InterruptRequested as e:
                return self._create_interrupt_result(e, message.tool_calls)
            except ConfirmationRequested as e:
                return self._create_confirmation_result(e, message.tool_calls)
            return None  # continue loop for more responses

        return AgentRunResult(
            state=AgentState.COMPLETED,
            content=message.content,
        )

    def _create_interrupt_result(
        self,
        interrupt: InterruptRequested,
        tool_calls: list[ToolCall],
    ) -> AgentRunResult:
        """Create an interrupt result and store state for resumption."""
        # find remaining tool calls after the interrupted one
        remaining = []
        found_interrupted = False
        for tc in tool_calls:
            if tc.id == interrupt.tool_call_id:
                found_interrupted = True
                continue
            if found_interrupted:
                remaining.append(tc)

        self._pending_interrupt = InterruptInfo(
            tool_name=interrupt.tool_name,
            tool_call_id=interrupt.tool_call_id,
            question=interrupt.question,
            context=interrupt.context,
        )
        self._pending_tool_calls = remaining if remaining else None

        return AgentRunResult(
            state=AgentState.INTERRUPTED,
            interrupt=self._pending_interrupt,
        )

    def _create_confirmation_result(
        self,
        conf: ConfirmationRequested,
        tool_calls: list[ToolCall],
    ) -> AgentRunResult:
        """Create a confirmation result and store state for resumption."""
        remaining = [tc for tc in tool_calls if tc.id != conf.tool_call_id]
        self._pending_confirmation = ConfirmationInfo(
            tool_name=conf.tool_name,
            tool_call_id=conf.tool_call_id,
            message=conf.message,
            operation=conf.operation,
            arguments=conf.arguments,
        )
        self._pending_tool_calls = remaining if remaining else None
        return AgentRunResult(
            state=AgentState.AWAITING_CONFIRMATION,
            confirmation=self._pending_confirmation,
        )

    def _is_auto_approved(self, operation: str, value: str) -> bool:
        """Check if an operation is auto-approved by configured patterns."""
        patterns = self.auto_approve_patterns.get(operation, [])
        return any(fnmatch.fnmatch(value, p) for p in patterns)

    def _add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add a tool result to conversation history."""
        self.history.append(UnifiedMessage(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        ))

    def _execute_single_tool(
        self, tool: BaseTool, tool_call_id: str, arguments: dict, verbose: bool
    ) -> str:
        """Execute a single tool and return result."""
        if getattr(tool, "INTERRUPT_TOOL", False):
            result = tool.execute(**arguments, _tool_call_id=tool_call_id)
        else:
            result = tool.execute(**arguments)
        if verbose:
            print(f"  Result: {result}")
        return str(result)

    def _execute_tool_calls(self, tool_calls: list[ToolCall], verbose: bool = False) -> None:
        """Execute tool calls and add results to history.

        Args:
            tool_calls: List of tool calls to execute
            verbose: Whether to print verbose output

        Raises:
            InterruptRequested: If a tool requests user input
        """
        for tool_call in tool_calls:
            tool_name = tool_call.name

            if tool_name not in self.tools:
                error_msg = f"Tool '{tool_name}' not found"
                print(f"Error: {error_msg}")
                self.history.append(UnifiedMessage(
                    role=MessageRole.TOOL,
                    content=error_msg,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                ))
                continue

            tool = self.tools[tool_name]

            # check if confirmation is required
            if getattr(tool, "REQUIRES_CONFIRMATION", False):
                op_type = getattr(tool, "OPERATION_TYPE", "")
                check_arg = getattr(tool, "CONFIRMATION_CHECK_ARG", "path")
                check_value = tool_call.arguments.get(check_arg, "")
                if not self._is_auto_approved(op_type, check_value):
                    raise ConfirmationRequested(
                        tool_name=tool_name,
                        tool_call_id=tool_call.id,
                        message=tool.get_confirmation_message(**tool_call.arguments),
                        operation=op_type,
                        arguments=tool_call.arguments,
                    )

            if verbose:
                print(f"[Verbose] Executing tool '{tool_name}' (ID: {tool_call.id})")
                print(f"  Args: {tool_call.arguments}")
            else:
                print(f"Executing tool: {tool_name} with args: {tool_call.arguments}")

            try:
                result = self._execute_single_tool(
                    tool, tool_call.id, tool_call.arguments, verbose
                )
                self._add_tool_result(tool_call.id, tool_name, result)
            except (InterruptRequested, ConfirmationRequested):
                raise
            except Exception as e:
                error_msg = f"Tool execution failed: {e}"
                print(f"Error: {error_msg}")
                self._add_tool_result(tool_call.id, tool_name, error_msg)

    def clear_history(self) -> None:
        """Clear conversation history, keeping only the system prompt."""
        system_msg = self.history[0] if self.history else None
        self.history = []
        if system_msg and system_msg.role == MessageRole.SYSTEM:
            self.history.append(system_msg)
        # clear interrupt state
        self._pending_interrupt = None
        self._pending_tool_calls = None

    def get_history(self) -> list[dict]:
        """Get conversation history as list of dicts.

        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in self.history]

    def visualize(self) -> str:
        """Generate a Mermaid diagram of the agent structure.

        Returns:
            Mermaid diagram string
        """
        from .visualizer import AgentVisualizer
        visualizer = AgentVisualizer(list(self.tools.values()))
        return visualizer.generate_mermaid_graph()
