"""Stream handling for LLM responses.

This module provides the StreamHandler class which processes streaming
responses from LLM clients and reconstructs them into UnifiedMessage objects.
"""

import json
from typing import Iterator

from .types import (
    MessageRole,
    StreamChunk,
    ToolCall,
    UnifiedMessage,
)
from .utils.stream_parser import StreamReasoningParser


class StreamHandler:
    """Handles streaming responses from LLM clients.

    Processes StreamChunk objects and reconstructs them into a UnifiedMessage,
    handling:
    - Text content accumulation
    - Reasoning content (both direct field and embedded tags)
    - Tool call delta reconstruction
    - Verbose output during streaming
    """

    def __init__(self, verbose: bool = False):
        """Initialize the stream handler.

        Args:
            verbose: Whether to print verbose output during streaming.
        """
        self.verbose = verbose
        self._parser = StreamReasoningParser()

    def process_stream(self, stream: Iterator[StreamChunk]) -> UnifiedMessage:
        """Process a stream and return the reconstructed message.

        Args:
            stream: Iterator of StreamChunk objects from the LLM client.

        Returns:
            The reconstructed UnifiedMessage with content, reasoning, and tool calls.
        """
        content = ""
        reasoning_content = ""
        tool_call_builders: dict[int, dict] = {}

        has_printed_agent_prefix = False
        is_reasoning = False

        if not self.verbose:
            print("Agent: ", end="", flush=True)
            has_printed_agent_prefix = True

        for chunk in stream:
            # handle reasoning from direct field
            if chunk.delta_reasoning:
                reasoning_content += chunk.delta_reasoning
                if self.verbose:
                    if not is_reasoning:
                        print("\n[Reasoning]: ", end="", flush=True)
                        is_reasoning = True
                    print(chunk.delta_reasoning, end="", flush=True)

            # handle text content
            if chunk.delta_content:
                result = self._process_content_chunk(
                    chunk.delta_content,
                    reasoning_content,
                    has_printed_agent_prefix,
                    is_reasoning,
                )
                content += result["content"]
                reasoning_content += result["reasoning"]
                has_printed_agent_prefix = result["has_prefix"]
                is_reasoning = result["is_reasoning"]

            # handle tool call deltas
            if chunk.delta_tool_call:
                self._process_tool_call_chunk(chunk.delta_tool_call, tool_call_builders)

        print()  # newline after stream

        # clean up any lingering reasoning state for display
        if is_reasoning and self.verbose:
            print()

        # build final tool calls
        tool_calls = self._build_tool_calls(tool_call_builders)

        if self.verbose and tool_calls:
            self._print_tool_calls_verbose(tool_calls)

        return UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content=content if content else None,
            reasoning_content=reasoning_content if reasoning_content else None,
            tool_calls=tool_calls if tool_calls else None,
        )

    def _process_content_chunk(
        self,
        chunk_content: str,
        existing_reasoning: str,
        has_printed_agent_prefix: bool,
        is_reasoning: bool,
    ) -> dict:
        """Process a content chunk, handling embedded reasoning tags.

        Args:
            chunk_content: The text content from the chunk.
            existing_reasoning: Reasoning content accumulated so far.
            has_printed_agent_prefix: Whether "Agent: " has been printed.
            is_reasoning: Whether we're currently in reasoning mode.

        Returns:
            Dict with keys: content, reasoning, has_prefix, is_reasoning
        """
        content = ""
        reasoning = ""

        # if we have explicit reasoning from field, just treat content as content
        if existing_reasoning and not self._parser.is_inside_think_tag:
            if not has_printed_agent_prefix:
                print("Agent: ", end="", flush=True)
                has_printed_agent_prefix = True
            print(chunk_content, end="", flush=True)
            return {
                "content": chunk_content,
                "reasoning": "",
                "has_prefix": has_printed_agent_prefix,
                "is_reasoning": is_reasoning,
            }

        # use parser to handle potential embedded tags
        for text_part, is_part_reasoning in self._parser.process_chunk(chunk_content):
            if is_part_reasoning:
                # inside reasoning block
                reasoning += text_part
                if self.verbose:
                    if not is_reasoning:
                        print("\n[Reasoning]: ", end="", flush=True)
                        is_reasoning = True
                    print(text_part, end="", flush=True)
            else:
                # standard content
                if is_reasoning:
                    if self.verbose:
                        print("\n", end="", flush=True)
                    is_reasoning = False

                if not has_printed_agent_prefix:
                    print("Agent: ", end="", flush=True)
                    has_printed_agent_prefix = True
                print(text_part, end="", flush=True)
                content += text_part

        return {
            "content": content,
            "reasoning": reasoning,
            "has_prefix": has_printed_agent_prefix,
            "is_reasoning": is_reasoning,
        }

    def _process_tool_call_chunk(
        self,
        delta: "PartialToolCall",
        builders: dict[int, dict],
    ) -> None:
        """Process a tool call delta chunk.

        Args:
            delta: The partial tool call delta.
            builders: Dict of tool call builders indexed by position.
        """
        index = delta.index

        if index not in builders:
            builders[index] = {
                "id": delta.id,
                "name": delta.name,
                "arguments": "",
            }

        builder = builders[index]
        if delta.id and not builder["id"]:
            builder["id"] = delta.id
        if delta.name and not builder["name"]:
            builder["name"] = delta.name
        if delta.arguments_delta:
            builder["arguments"] += delta.arguments_delta

    def _build_tool_calls(self, builders: dict[int, dict]) -> list[ToolCall]:
        """Build final ToolCall objects from accumulated builders.

        Args:
            builders: Dict of tool call builders indexed by position.

        Returns:
            List of complete ToolCall objects.
        """
        tool_calls = []
        for index, builder in builders.items():
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
        return tool_calls

    def _print_tool_calls_verbose(self, tool_calls: list[ToolCall]) -> None:
        """Print tool calls in verbose mode.

        Args:
            tool_calls: List of tool calls to print.
        """
        print(f"\n[Verbose] Generated {len(tool_calls)} tool calls:")
        for tc in tool_calls:
            print(f"  - ID: {tc.id}")
            print(f"    Name: {tc.name}")
            print(f"    Arguments: {tc.arguments}")


# import for type hint
from .types import PartialToolCall  # noqa: E402
