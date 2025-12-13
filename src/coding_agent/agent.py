"""Main agent implementation.

The CodingAgent orchestrates conversations between the user, LLM, and tools.
It uses unified types for all interactions, making it provider-agnostic.
"""

from typing import Iterator

from .clients.base import BaseLLMClient
from .core import MemoryManager, PromptBuilder, ToolExecutor
from .exceptions import ConfirmationRequested, InterruptRequested
from .stream_handler import StreamHandler
from .tools.base import BaseTool
from .types import (
    AgentRunResult,
    AgentState,
    ConfirmationInfo,
    InterruptInfo,
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
        self.tool_list = tools

        # initialize components
        self.prompt_builder = PromptBuilder(system_prompt)
        self.tool_executor = ToolExecutor(
            tools={tool.name: tool for tool in tools},
            auto_approve_patterns=auto_approve_patterns,
        )
        self.memory = MemoryManager()

        # initialize conversation with system prompt
        formatted_prompt = self.prompt_builder.format_system_prompt(tools, client)
        self.memory.add_message(
            self.prompt_builder.build_system_message(formatted_prompt)
        )

    # legacy property for backwards compatibility
    @property
    def tools(self) -> dict[str, BaseTool]:
        """Get tools dictionary (for backwards compatibility)."""
        return self.tool_executor.tools

    @property
    def history(self) -> list[UnifiedMessage]:
        """Get conversation history (for backwards compatibility)."""
        return self.memory.history

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
        # clean up any pending state to avoid corrupted history
        self.memory.cleanup_pending_state()

        self.memory.add_message(
            self.prompt_builder.build_user_message(user_input)
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
        interrupt = self.memory.pending_interrupt
        if not interrupt:
            raise ValueError("No pending interrupt to resume")

        if interrupt.tool_call_id != tool_call_id:
            raise ValueError(
                f"Tool call ID mismatch: expected {interrupt.tool_call_id}, "
                f"got {tool_call_id}"
            )

        # add the user's response as a tool result
        self.memory.add_message(
            self.prompt_builder.build_tool_result(
                tool_call_id, interrupt.tool_name, user_response
            )
        )

        # process remaining tool calls if any
        _, remaining_calls = self.memory.clear_interrupt()
        remaining_calls = remaining_calls or []

        if remaining_calls:
            try:
                self.tool_executor.execute_tool_calls(
                    remaining_calls, self.memory, verbose=verbose
                )
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
        conf = self.memory.pending_confirmation
        if not conf:
            raise ValueError("No pending confirmation to resume")

        if conf.tool_call_id != tool_call_id:
            raise ValueError(
                f"Tool call ID mismatch: expected {conf.tool_call_id}, "
                f"got {tool_call_id}"
            )

        tool_name = conf.tool_name
        arguments = conf.arguments
        _, remaining_calls = self.memory.clear_confirmation()
        remaining_calls = remaining_calls or []

        if confirmed:
            tool = self.tool_executor.get_tool(tool_name)
            if tool:
                try:
                    result = self.tool_executor.execute_single_tool(
                        tool, tool_call_id, arguments, verbose
                    )
                    self.memory.add_tool_result(tool_call_id, tool_name, result)
                except InterruptRequested as e:
                    if remaining_calls:
                        self.memory.set_pending_interrupt(
                            InterruptInfo(
                                tool_name=e.tool_name,
                                tool_call_id=e.tool_call_id,
                                question=e.question,
                                context=e.context,
                            ),
                            remaining_calls,
                        )
                    return self._create_interrupt_result(e, [])
                except Exception as e:
                    error_msg = f"Tool execution failed: {e}"
                    print(f"Error: {error_msg}")
                    self.memory.add_tool_result(tool_call_id, tool_name, error_msg)
        else:
            self.memory.add_tool_result(
                tool_call_id, tool_name,
                f"Operation cancelled by user: {tool_name} was not executed. "
                "Do not retry this operation - inform the user that it was cancelled."
            )

        # process remaining tool calls if any
        if remaining_calls:
            try:
                self.tool_executor.execute_tool_calls(
                    remaining_calls, self.memory, verbose=verbose
                )
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
                messages=self.memory.history,
                tools=self.tool_list if self.tool_executor.tools else None,
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

            self.memory.add_message(message)

            # handle tool calls or return completed result
            result = self._process_message(message, verbose)
            if result is not None:
                return result

    def _print_response(self, message: UnifiedMessage, verbose: bool) -> None:
        """Print response content for non-streaming mode."""
        if verbose and message.reasoning_content:
            print(f"\n[Reasoning]: {message.reasoning_content}")
        if message.content:
            print(f"Agent: {message.content}")

    def _process_message(
        self,
        message: UnifiedMessage,
        verbose: bool,
    ) -> AgentRunResult | None:
        """Process a message, executing tool calls or returning completion."""
        if message.tool_calls:
            try:
                self.tool_executor.execute_tool_calls(
                    message.tool_calls, self.memory, verbose=verbose
                )
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

        info = InterruptInfo(
            tool_name=interrupt.tool_name,
            tool_call_id=interrupt.tool_call_id,
            question=interrupt.question,
            context=interrupt.context,
        )
        self.memory.set_pending_interrupt(info, remaining if remaining else None)

        return AgentRunResult(
            state=AgentState.INTERRUPTED,
            interrupt=info,
        )

    def _create_confirmation_result(
        self,
        conf: ConfirmationRequested,
        tool_calls: list[ToolCall],
    ) -> AgentRunResult:
        """Create a confirmation result and store state for resumption."""
        remaining = [tc for tc in tool_calls if tc.id != conf.tool_call_id]
        info = ConfirmationInfo(
            tool_name=conf.tool_name,
            tool_call_id=conf.tool_call_id,
            message=conf.message,
            operation=conf.operation,
            arguments=conf.arguments,
        )
        self.memory.set_pending_confirmation(info, remaining if remaining else None)

        return AgentRunResult(
            state=AgentState.AWAITING_CONFIRMATION,
            confirmation=info,
        )

    def clear_history(self) -> None:
        """Clear conversation history, keeping only the system prompt."""
        self.memory.clear(keep_system=True)

    def get_history(self) -> list[dict]:
        """Get conversation history as list of dicts."""
        return self.memory.get_history()

    def visualize(self) -> str:
        """Generate a Mermaid diagram of the agent structure."""
        from .visualizer import AgentVisualizer
        visualizer = AgentVisualizer(list(self.tool_executor.tools.values()))
        return visualizer.generate_mermaid_graph()
