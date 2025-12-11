"""Anthropic client implementation.

This client handles communication with the Anthropic API (Claude models)
and normalizes responses to the unified format.

Anthropic has unique requirements:
- System prompt is passed separately, not in messages
- Tool calls use content blocks with type "tool_use"
- Tool results go in user messages with type "tool_result"
- Extended thinking uses a separate "thinking" parameter with budget_tokens

Supported models with extended thinking:
- claude-opus-4-5-20251101
- claude-sonnet-4-5-20250929
- claude-sonnet-4-20250514
- claude-haiku-4-5-20251001
"""

import os
from typing import Any, Iterator

from anthropic import Anthropic, APIConnectionError
from anthropic import AuthenticationError as AnthropicAuthError
from anthropic import RateLimitError as AnthropicRateLimitError

from ..exceptions import (
    AuthenticationError,
    InvalidResponseError,
    ProviderUnavailableError,
    RateLimitError,
)
from ..tools.base import BaseTool
from ..types import (
    FinishReason,
    MessageRole,
    PartialToolCall,
    StreamChunk,
    ToolCall,
    UnifiedMessage,
    UnifiedResponse,
    UsageStats,
)
from .base import BaseLLMClient

# supported configuration keys for anthropic
SUPPORTED_CONFIG_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "stop_sequences",
    # extended thinking
    "thinking_enabled",
    "thinking_budget_tokens",
    # tool choice
    "tool_choice",
}


class AnthropicClient(BaseLLMClient):
    """Anthropic API client with unified response handling.

    Supports:
    - Extended thinking with budget_tokens configuration
    - Generation parameters: temperature, top_p, top_k, stop_sequences
    - Tool choice configuration: auto, any, none, or specific tool
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5-20250929",
        client_config: dict | None = None,
    ):
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to Claude Sonnet 4.5.
            client_config: Optional configuration parameters:
                - temperature: float (0.0-1.0, default 1.0)
                - top_p: float (nucleus sampling)
                - top_k: int (top-k sampling)
                - max_tokens: int (default 4096)
                - stop_sequences: list[str]
                - thinking_enabled: bool (enable extended thinking)
                - thinking_budget_tokens: int (min 1024, must be < max_tokens)
                - tool_choice: dict (e.g., {"type": "auto"}, {"type": "tool", "name": "..."})
        """
        super().__init__(client_config)
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the client configuration."""
        if not self.client_config:
            return

        # check for unsupported keys
        unsupported = set(self.client_config.keys()) - SUPPORTED_CONFIG_KEYS
        if unsupported:
            raise ValueError(f"Unsupported config keys for Anthropic: {unsupported}")

        # validate thinking configuration
        thinking_enabled = self.client_config.get("thinking_enabled", False)
        budget_tokens = self.client_config.get("thinking_budget_tokens")
        max_tokens = self.client_config.get("max_tokens", 4096)

        if thinking_enabled and budget_tokens:
            if budget_tokens < 1024:
                raise ValueError("thinking_budget_tokens must be at least 1024")
            if budget_tokens >= max_tokens:
                raise ValueError("thinking_budget_tokens must be less than max_tokens")

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

        # build kwargs with configuration
        kwargs = self._build_api_kwargs(system_prompt, converted_messages, converted_tools)

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

    def _build_api_kwargs(
        self,
        system_prompt: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build the API kwargs from configuration."""
        config = self.client_config or {}

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": config.get("max_tokens", 4096),
        }

        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        # generation parameters
        if "temperature" in config:
            kwargs["temperature"] = config["temperature"]
        if "top_p" in config:
            kwargs["top_p"] = config["top_p"]
        if "top_k" in config:
            kwargs["top_k"] = config["top_k"]
        if "stop_sequences" in config:
            kwargs["stop_sequences"] = config["stop_sequences"]

        # extended thinking
        if config.get("thinking_enabled"):
            budget_tokens = config.get("thinking_budget_tokens", 1024)
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget_tokens,
            }

        # tool choice (only if tools provided)
        if tools and "tool_choice" in config:
            kwargs["tool_choice"] = config["tool_choice"]

        return kwargs

    def _convert_messages(
        self, messages: list[UnifiedMessage]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert unified messages to Anthropic format."""
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
            reasoning_content = ""

            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "thinking":
                    reasoning_content += block.thinking
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
                    reasoning_content=reasoning_content if reasoning_content else None,
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
        event_type = getattr(chunk, "type", None)

        if event_type == "content_block_delta":
            delta = chunk.delta
            delta_type = getattr(delta, "type", None)

            if delta_type == "text_delta":
                return StreamChunk(delta_content=delta.text)
            elif delta_type == "thinking_delta":
                return StreamChunk(delta_reasoning=delta.thinking)
            elif delta_type == "input_json_delta":
                return StreamChunk(
                    delta_tool_call=PartialToolCall(
                        index=chunk.index,
                        arguments_delta=delta.partial_json,
                    )
                )

        elif event_type == "content_block_start":
            block = chunk.content_block
            block_type = getattr(block, "type", None)

            if block_type == "tool_use":
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
            stop_reason = getattr(chunk.delta, "stop_reason", None)
            if stop_reason == "tool_use":
                return StreamChunk(finish_reason=FinishReason.TOOL_USE)
            elif stop_reason == "max_tokens":
                return StreamChunk(finish_reason=FinishReason.LENGTH)
            elif stop_reason == "end_turn":
                return StreamChunk(finish_reason=FinishReason.STOP)

        return StreamChunk()

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        with response as stream:
            for event in stream:
                chunk = self._parse_stream_chunk(event)
                if (chunk.delta_content or chunk.delta_reasoning or
                        chunk.delta_tool_call or chunk.finish_reason):
                    yield chunk
