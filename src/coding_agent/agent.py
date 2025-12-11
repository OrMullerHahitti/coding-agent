"""Main agent implementation.

The CodingAgent orchestrates conversations between the user, LLM, and tools.
It uses unified types for all interactions, making it provider-agnostic.
"""

from typing import Iterator

from .clients.base import BaseLLMClient
from .exceptions import InterruptRequested
from .stream_handler import StreamHandler
from .tools.base import BaseTool
from .types import (
    AgentRunResult,
    AgentState,
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
    """

    def __init__(
        self,
        client: BaseLLMClient,
        tools: list[BaseTool],
        system_prompt: str = "You are a helpful coding assistant.",
    ):
        """Initialize the agent.

        Args:
            client: The LLM client to use (provider-agnostic)
            tools: List of tools available to the LLM
            system_prompt: System prompt for the conversation
        """
        self.client = client
        self.tools = {tool.name: tool for tool in tools}
        self.tool_list = tools

        formatted_prompt = self.client.format_system_prompt(system_prompt, tools)
        self.history: list[UnifiedMessage] = [
            UnifiedMessage(role=MessageRole.SYSTEM, content=formatted_prompt)
        ]

        # state for interrupt handling
        self._pending_interrupt: InterruptInfo | None = None
        self._pending_tool_calls: list[ToolCall] | None = None

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
            if verbose:
                print(f"[Verbose] Executing tool '{tool_name}' (ID: {tool_call.id})")
                print(f"  Args: {tool_call.arguments}")
            else:
                print(f"Executing tool: {tool_name} with args: {tool_call.arguments}")

            try:
                # check if tool supports interrupt mode
                if getattr(tool, "INTERRUPT_TOOL", False):
                    # pass tool_call_id for interrupt handling
                    result = tool.execute(**tool_call.arguments, _tool_call_id=tool_call.id)
                else:
                    result = tool.execute(**tool_call.arguments)

                if verbose:
                    print(f"  Result: {result}")

                self.history.append(UnifiedMessage(
                    role=MessageRole.TOOL,
                    content=str(result),
                    tool_call_id=tool_call.id,
                    name=tool_name,
                ))
            except InterruptRequested:
                # re-raise interrupt exceptions - don't catch them as errors
                raise
            except Exception as e:
                error_msg = f"Tool execution failed: {e}"
                print(f"Error: {error_msg}")
                self.history.append(UnifiedMessage(
                    role=MessageRole.TOOL,
                    content=error_msg,
                    tool_call_id=tool_call.id,
                    name=tool_name,
                ))

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
