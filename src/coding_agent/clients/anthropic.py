"""Anthropic client implementation.

This client handles communication with the Anthropic API (Claude models)
and normalizes responses to the unified format.

Anthropic has unique requirements:
- System prompt is passed separately, not in messages
- Tool calls use content blocks with type "tool_use"
- Tool results go in user messages with type "tool_result"
"""

import os
from typing import Any, Iterator

from anthropic import Anthropic
from anthropic import (
    APIConnectionError,
    RateLimitError as AnthropicRateLimitError,
    AuthenticationError as AnthropicAuthError,
)

from .base import BaseLLMClient
from ..tools.base import BaseTool
from ..types import (
    UnifiedMessage,
    UnifiedResponse,
    StreamChunk,
    MessageRole,
    FinishReason,
    ToolCall,
    PartialToolCall,
    UsageStats,
)
from ..exceptions import (
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
    InvalidResponseError,
)


class AnthropicClient(BaseLLMClient):
    """Anthropic API client with unified response handling."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20240620",
    ):
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to Claude 3.5 Sonnet.
        """
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from Anthropic.

        Args:
            messages: Conversation history in unified format
            tools: Optional list of tools available to the model
            stream: Whether to stream the response

        Returns:
            UnifiedResponse for non-streaming, Iterator[StreamChunk] for streaming

        Raises:
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
            ProviderUnavailableError: If API is unavailable
        """
        system_prompt, converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": 4096,
        }

        if system_prompt:
            kwargs["system"] = system_prompt
        if converted_tools:
            kwargs["tools"] = converted_tools

        try:
            if stream:
                response = self.client.messages.stream(**kwargs)
                return self._stream_response(response)
            else:
                response = self.client.messages.create(**kwargs)
                return self._parse_response(response)

        except AnthropicAuthError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {e}") from e
        except AnthropicRateLimitError as e:
            raise RateLimitError("Anthropic rate limit exceeded") from e
        except APIConnectionError as e:
            raise ProviderUnavailableError(f"Anthropic API unavailable: {e}") from e

    def _convert_messages(
        self, messages: list[UnifiedMessage]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert unified messages to Anthropic format.

        Anthropic requires:
        - System prompt separate from messages
        - Tool calls as content blocks with type "tool_use"
        - Tool results as user messages with type "tool_result"

        Returns:
            Tuple of (system_prompt, converted_messages)
        """
        system_prompt = None
        converted = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content

            elif msg.role == MessageRole.USER:
                converted.append({"role": "user", "content": msg.content})

            elif msg.role == MessageRole.ASSISTANT:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                converted.append({"role": "assistant", "content": content})

            elif msg.role == MessageRole.TOOL:
                # Anthropic expects tool results in user message with tool_result block
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })

        return system_prompt, converted

    def _convert_tools(self, tools: list[BaseTool]) -> list[dict[str, Any]]:
        """Convert tools to Anthropic format with input_schema."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any) -> UnifiedResponse:
        """Parse Anthropic response into unified format."""
        try:
            tool_calls = []
            text_content = ""

            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    ))

            finish_map = {
                "end_turn": FinishReason.STOP,
                "tool_use": FinishReason.TOOL_USE,
                "max_tokens": FinishReason.LENGTH,
            }

            return UnifiedResponse(
                message=UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content=text_content if text_content else None,
                    tool_calls=tool_calls if tool_calls else None,
                ),
                finish_reason=finish_map.get(response.stop_reason, FinishReason.STOP),
                usage=UsageStats(
                    prompt_tokens=response.usage.input_tokens,
                    completion_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                ),
            )
        except Exception as e:
            raise InvalidResponseError(f"Failed to parse Anthropic response: {e}") from e

    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a single streaming chunk from Anthropic."""
        # Anthropic streaming events have different types
        event_type = getattr(chunk, "type", None)

        if event_type == "content_block_delta":
            delta = chunk.delta
            if delta.type == "text_delta":
                return StreamChunk(delta_content=delta.text)
            elif delta.type == "input_json_delta":
                # Tool argument streaming
                return StreamChunk(
                    delta_tool_call=PartialToolCall(
                        index=chunk.index,
                        arguments_delta=delta.partial_json,
                    )
                )

        elif event_type == "content_block_start":
            block = chunk.content_block
            if block.type == "tool_use":
                return StreamChunk(
                    delta_tool_call=PartialToolCall(
                        index=chunk.index,
                        id=block.id,
                        name=block.name,
                    )
                )

        elif event_type == "message_stop":
            return StreamChunk(finish_reason=FinishReason.STOP)

        elif event_type == "message_delta":
            if chunk.delta.stop_reason == "tool_use":
                return StreamChunk(finish_reason=FinishReason.TOOL_USE)
            elif chunk.delta.stop_reason == "max_tokens":
                return StreamChunk(finish_reason=FinishReason.LENGTH)

        return StreamChunk()

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        with response as stream:
            for event in stream:
                chunk = self._parse_stream_chunk(event)
                # Only yield non-empty chunks
                if chunk.delta_content or chunk.delta_tool_call or chunk.finish_reason:
                    yield chunk
