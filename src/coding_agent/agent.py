"""Main agent implementation.

The CodingAgent orchestrates conversations between the user, LLM, and tools.
It uses unified types for all interactions, making it provider-agnostic.
"""

import json
from typing import Iterator

from .clients.base import BaseLLMClient
from .tools.base import BaseTool
from .types import (
    UnifiedMessage,
    UnifiedResponse,
    StreamChunk,
    MessageRole,
    FinishReason,
    ToolCall,
    PartialToolCall,
    AgentState,
    InterruptInfo,
    AgentRunResult,
)
from .exceptions import (
    ToolNotFoundError,
    ToolExecutionError,
    ToolValidationError,
    InterruptRequested,
)
from .utils.stream_parser import StreamReasoningParser


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

            if stream:
                # handle streaming response
                assert isinstance(response, Iterator)
                final_message = self._handle_stream(response, verbose=verbose)
                self.history.append(final_message)

                if final_message.tool_calls:
                    try:
                        self._execute_tool_calls(final_message.tool_calls, verbose=verbose)
                    except InterruptRequested as e:
                        return self._create_interrupt_result(e, final_message.tool_calls)
                else:
                    return AgentRunResult(
                        state=AgentState.COMPLETED,
                        content=final_message.content,
                    )
            else:
                # handle non-streaming response
                assert isinstance(response, UnifiedResponse)
                self.history.append(response.message)

                if response.message.tool_calls:
                    try:
                        self._execute_tool_calls(response.message.tool_calls, verbose=verbose)
                    except InterruptRequested as e:
                        return self._create_interrupt_result(e, response.message.tool_calls)
                else:
                    if verbose and response.message.reasoning_content:
                        print(f"\n[Reasoning]: {response.message.reasoning_content}")
                    print(f"Agent: {response.message.content}")
                    return AgentRunResult(
                        state=AgentState.COMPLETED,
                        content=response.message.content,
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

    def _handle_stream(self, stream: Iterator[StreamChunk], verbose: bool = False) -> UnifiedMessage:
        """Handle a streaming response and reconstruct the message.

        Args:
            stream: Iterator of StreamChunk objects
            verbose: Whether to print verbose output

        Returns:
            The reconstructed UnifiedMessage
        """
        content = ""
        reasoning_content = ""
        tool_calls: list[ToolCall] = []
        tool_call_builders: dict[int, dict] = {}

        has_printed_agent_prefix = False
        is_reasoning = False

        # helper for parsing embedded tags (e.g. for DeepSeek)
        parser = StreamReasoningParser()

        if not verbose:
            print("Agent: ", end="", flush=True)
            has_printed_agent_prefix = True

        for chunk in stream:
            # handle reasoning from direct field
            if chunk.delta_reasoning:
                reasoning_content += chunk.delta_reasoning
                if verbose:
                    if not is_reasoning:
                        print("\n[Reasoning]: ", end="", flush=True)
                        is_reasoning = True
                    print(chunk.delta_reasoning, end="", flush=True)

            # handle text content
            if chunk.delta_content:
                chunk_content = chunk.delta_content

                # if we have explicit reasoning from field, just treat content as content
                if reasoning_content and not parser.is_inside_think_tag:
                    if not has_printed_agent_prefix:
                        print("Agent: ", end="", flush=True)
                        has_printed_agent_prefix = True
                    print(chunk_content, end="", flush=True)
                    content += chunk_content
                    continue

                # use parser to handle potential embedded tags
                for text_part, is_part_reasoning in parser.process_chunk(chunk_content):
                    if is_part_reasoning:
                        # inside reasoning block
                        reasoning_content += text_part
                        if verbose:
                            if not is_reasoning:
                                print("\n[Reasoning]: ", end="", flush=True)
                                is_reasoning = True
                            print(text_part, end="", flush=True)
                    else:
                        # standard content
                        if is_reasoning:
                            if verbose:
                                print("\n", end="", flush=True)
                            is_reasoning = False

                        if not has_printed_agent_prefix:
                            print("Agent: ", end="", flush=True)
                            has_printed_agent_prefix = True
                        print(text_part, end="", flush=True)
                        content += text_part

            # handle tool call deltas
            if chunk.delta_tool_call:
                delta = chunk.delta_tool_call
                index = delta.index

                if index not in tool_call_builders:
                    tool_call_builders[index] = {
                        "id": delta.id,
                        "name": delta.name,
                        "arguments": "",
                    }

                builder = tool_call_builders[index]
                if delta.id and not builder["id"]:
                    builder["id"] = delta.id
                if delta.name and not builder["name"]:
                    builder["name"] = delta.name
                if delta.arguments_delta:
                    builder["arguments"] += delta.arguments_delta

        print()  # newline after stream

        # convert builders to ToolCall objects
        for index, builder in tool_call_builders.items():
            if builder["name"]:  # only add if we have a name
                try:
                    args = json.loads(builder["arguments"]) if builder["arguments"] else {}
                    tool_calls.append(ToolCall(
                        id=builder["id"] or f"call_{index}",
                        name=builder["name"],
                        arguments=args,
                    ))
                except json.JSONDecodeError:
                    # in case of partial JSON or error, handle gracefully
                    pass

        # clean up any lingering reasoning state for display
        if is_reasoning and verbose:
            print()

        if verbose and tool_calls:
            print(f"\n[Verbose] Generated {len(tool_calls)} tool calls:")
            for tc in tool_calls:
                print(f"  - ID: {tc.id}")
                print(f"    Name: {tc.name}")
                print(f"    Arguments: {tc.arguments}")

        return UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content=content if content else None,
            reasoning_content=reasoning_content if reasoning_content else None,
            tool_calls=tool_calls if tool_calls else None,
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
