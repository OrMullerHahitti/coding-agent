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
)
from .exceptions import (
    ToolNotFoundError,
    ToolExecutionError,
    ToolValidationError,
)


class CodingAgent:
    """Agent that coordinates between LLM and tools.

    The agent maintains conversation history and handles the tool-use loop:
    1. Send messages to LLM
    2. If LLM requests tool calls, execute them
    3. Add tool results to history
    4. Repeat until LLM produces a final response
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
        self.history: list[UnifiedMessage] = [
            UnifiedMessage(role=MessageRole.SYSTEM, content=system_prompt)
        ]

    def run(self, user_input: str, stream: bool = False) -> str | None:
        """Run a conversation turn with the given user input.

        Args:
            user_input: The user's message
            stream: Whether to stream the response

        Returns:
            The final assistant response text, or None if streaming
        """
        self.history.append(
            UnifiedMessage(role=MessageRole.USER, content=user_input)
        )

        while True:
            response = self.client.generate(
                messages=self.history,
                tools=self.tool_list if self.tools else None,
                stream=stream,
            )

            if stream:
                # Handle streaming response
                assert isinstance(response, Iterator)
                final_message = self._handle_stream(response)
                self.history.append(final_message)

                if final_message.tool_calls:
                    self._execute_tool_calls(final_message.tool_calls)
                else:
                    return None  # Already printed during streaming
            else:
                # Handle non-streaming response
                assert isinstance(response, UnifiedResponse)
                self.history.append(response.message)

                if response.message.tool_calls:
                    self._execute_tool_calls(response.message.tool_calls)
                else:
                    print(f"Agent: {response.message.content}")
                    return response.message.content

    def _handle_stream(self, stream: Iterator[StreamChunk]) -> UnifiedMessage:
        """Handle a streaming response and reconstruct the message.

        Args:
            stream: Iterator of StreamChunk objects

        Returns:
            The reconstructed UnifiedMessage
        """
        content = ""
        tool_calls: list[ToolCall] = []
        tool_call_builders: dict[int, dict] = {}

        print("Agent: ", end="", flush=True)

        for chunk in stream:
            # Handle text content
            if chunk.delta_content:
                print(chunk.delta_content, end="", flush=True)
                content += chunk.delta_content

            # Handle tool call deltas
            if chunk.delta_tool_call:
                tc = chunk.delta_tool_call
                if tc.index not in tool_call_builders:
                    tool_call_builders[tc.index] = {
                        "id": "",
                        "name": "",
                        "arguments": "",
                    }

                builder = tool_call_builders[tc.index]
                if tc.id:
                    builder["id"] += tc.id
                if tc.name:
                    builder["name"] += tc.name
                if tc.arguments_delta:
                    builder["arguments"] += tc.arguments_delta

        print()  # Newline after stream

        # Convert builders to ToolCall objects
        for index in sorted(tool_call_builders.keys()):
            builder = tool_call_builders[index]
            try:
                arguments = json.loads(builder["arguments"]) if builder["arguments"] else {}
            except json.JSONDecodeError:
                arguments = {}

            tool_calls.append(ToolCall(
                id=builder["id"],
                name=builder["name"],
                arguments=arguments,
            ))

        return UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content=content if content else None,
            tool_calls=tool_calls if tool_calls else None,
        )

    def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Execute tool calls and add results to history.

        Args:
            tool_calls: List of tool calls to execute
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
            print(f"Executing tool: {tool_name} with args: {tool_call.arguments}")

            try:
                result = tool.execute(**tool_call.arguments)
                self.history.append(UnifiedMessage(
                    role=MessageRole.TOOL,
                    content=str(result),
                    tool_call_id=tool_call.id,
                    name=tool_name,
                ))
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
