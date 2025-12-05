"""OpenAI client implementation.

This client handles communication with the OpenAI API and normalizes
responses to the unified format.
"""

import json
import os
from typing import Any, Iterator

from openai import OpenAI, APIConnectionError, RateLimitError as OpenAIRateLimitError
from openai import AuthenticationError as OpenAIAuthError

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


class OpenAIClient(BaseLLMClient):
    """OpenAI API client with unified response handling."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            model: Model to use. Defaults to gpt-4o.
        """
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from OpenAI.

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
        converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools) if tools else None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=converted_messages,
                tools=converted_tools,
                tool_choice="auto" if converted_tools else None,
                stream=stream,
            )

            if stream:
                return self._stream_response(response)
            return self._parse_response(response)

        except OpenAIAuthError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}") from e
        except OpenAIRateLimitError as e:
            raise RateLimitError("OpenAI rate limit exceeded") from e
        except APIConnectionError as e:
            raise ProviderUnavailableError(f"OpenAI API unavailable: {e}") from e

    def _convert_messages(self, messages: list[UnifiedMessage]) -> list[dict[str, Any]]:
        """Convert unified messages to OpenAI format."""
        converted = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                converted.append({"role": "system", "content": msg.content})
            elif msg.role == MessageRole.USER:
                converted.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                converted.append(entry)
            elif msg.role == MessageRole.TOOL:
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })
        return converted

    def _convert_tools(self, tools: list[BaseTool]) -> list[dict[str, Any]]:
        """Convert tools to OpenAI function format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def _parse_response(self, response: Any) -> UnifiedResponse:
        """Parse OpenAI response into unified format."""
        try:
            choice = response.choices[0]
            message = choice.message

            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                    for tc in message.tool_calls
                ]

            finish_map = {
                "stop": FinishReason.STOP,
                "tool_calls": FinishReason.TOOL_USE,
                "length": FinishReason.LENGTH,
            }

            usage = None
            if response.usage:
                usage = UsageStats(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

            return UnifiedResponse(
                message=UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content=message.content,
                    tool_calls=tool_calls,
                ),
                finish_reason=finish_map.get(choice.finish_reason, FinishReason.STOP),
                usage=usage,
            )
        except Exception as e:
            raise InvalidResponseError(f"Failed to parse OpenAI response: {e}") from e

    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a single streaming chunk."""
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            return StreamChunk()

        delta = choice.delta
        finish_reason = None

        if choice.finish_reason:
            finish_map = {
                "stop": FinishReason.STOP,
                "tool_calls": FinishReason.TOOL_USE,
                "length": FinishReason.LENGTH,
            }
            finish_reason = finish_map.get(choice.finish_reason, FinishReason.STOP)

        delta_content = delta.content if hasattr(delta, "content") else None

        delta_tool_call = None
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            tc = delta.tool_calls[0]
            delta_tool_call = PartialToolCall(
                index=tc.index,
                id=tc.id if tc.id else None,
                name=tc.function.name if tc.function and tc.function.name else None,
                arguments_delta=tc.function.arguments if tc.function and tc.function.arguments else None,
            )

        return StreamChunk(
            delta_content=delta_content,
            delta_tool_call=delta_tool_call,
            finish_reason=finish_reason,
        )

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        for chunk in response:
            yield self._parse_stream_chunk(chunk)
