"""Base class for OpenAI-compatible API clients.

This class provides shared implementation for providers that use the
OpenAI-compatible API format (OpenAI, Together, Groq, etc.).
"""

import json
from abc import abstractmethod
from contextlib import contextmanager
from typing import Any, Iterator

from ..exceptions import InvalidResponseError
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


class OpenAICompatibleClient(BaseLLMClient):
    """Base class for clients using OpenAI-compatible API format.

    Subclasses must implement:
    - _create_client(): initialize the provider SDK client
    - _get_supported_config_keys(): return set of supported config parameters
    - _get_default_api_args(): return provider-specific default arguments
    - _handle_api_errors(): context manager for exception mapping
    - _parse_stream_chunk(): provider-specific stream chunk parsing
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        client_config: dict | None = None,
    ):
        """Initialize the client.

        Args:
            api_key: API key for the provider
            model: Model name to use
            client_config: Optional configuration parameters
        """
        super().__init__(client_config)
        self.model = model
        self.client = self._create_client(api_key)

    @abstractmethod
    def _create_client(self, api_key: str | None) -> Any:
        """Create the provider's SDK client instance.

        Args:
            api_key: API key for authentication

        Returns:
            Initialized SDK client
        """
        pass

    @abstractmethod
    def _get_supported_config_keys(self) -> set[str]:
        """Return the set of config keys supported by this provider.

        Returns:
            Set of supported parameter names (e.g., temperature, max_tokens)
        """

    @abstractmethod
    def _get_default_api_args(self) -> dict[str, Any]:
        """Return provider-specific default API arguments.

        Returns:
            Dict of default arguments (e.g., max_tokens for Together)
        """


    @abstractmethod
    @contextmanager
    def _handle_api_errors(self):
        """Context manager for handling provider-specific errors.

        Should catch provider exceptions and re-raise as our exceptions:
        - AuthenticationError
        - RateLimitError
        - ProviderUnavailableError
        """

    # ==================== shared implementations ====================

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from the provider.

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

        # build api_args with defaults, then apply config overrides
        api_args = {
            "model": self.model,
            "messages": converted_messages,
            "tools": converted_tools,
            "tool_choice": "auto" if converted_tools else None,
            "stream": stream,
            **self._get_default_api_args(),
        }

        # apply config overrides for supported keys
        if self.client_config:
            supported_keys = self._get_supported_config_keys()
            for key, value in self.client_config.items():
                if key in supported_keys:
                    api_args[key] = value

        with self._handle_api_errors():
            response = self.client.chat.completions.create(**api_args)
            if stream:
                return self._stream_response(response)
            return self._parse_response(response)

    def _convert_messages(self, messages: list[UnifiedMessage]) -> list[dict[str, Any]]:
        """Convert unified messages to OpenAI-compatible format."""
        return [self._convert_message(msg) for msg in messages]

    def _convert_message(self, message: UnifiedMessage) -> dict[str, Any]:
        """Convert a single unified message to OpenAI-compatible format."""
        if message.role == MessageRole.SYSTEM:
            return {"role": "system", "content": message.content}
        if message.role == MessageRole.USER:
            return {"role": "user", "content": message.content}
        if message.role == MessageRole.ASSISTANT:
            return self._convert_assistant_message(message)
        if message.role == MessageRole.TOOL:
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "content": message.content,
            }
        return {"role": "user", "content": str(message.content)}

    def _convert_assistant_message(self, message: UnifiedMessage) -> dict[str, Any]:
        """Convert assistant message handling tool calls."""
        entry: dict[str, Any] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in message.tool_calls
            ]
        return entry

    def _map_finish_reason(self, reason: str | None) -> FinishReason:
        """Map OpenAI-compatible finish reason to unified FinishReason."""
        if not reason:
            return FinishReason.STOP
        mapping = {
            "stop": FinishReason.STOP,
            "tool_calls": FinishReason.TOOL_USE,
            "length": FinishReason.LENGTH,
        }
        return mapping.get(reason, FinishReason.STOP)

    def _convert_tools(self, tools: list[BaseTool]) -> list[dict[str, Any]]:
        """Convert tools to OpenAI-compatible function format."""
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
        """Parse OpenAI-compatible response into unified format."""
        try:
            choice = response.choices[0]
            message = choice.message

            # check for reasoning field (primary) then reasoning_content (fallback)
            reasoning_content = getattr(message, "reasoning", None) or getattr(
                message, "reasoning_content", None
            )

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
                    reasoning_content=reasoning_content,
                    tool_calls=tool_calls,
                ),
                finish_reason=self._map_finish_reason(choice.finish_reason),
                usage=usage,
            )
        except Exception as e:
            raise InvalidResponseError(
                f"Failed to parse {self.__class__.__name__} response: {e}"
            ) from e

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        for chunk in response:
            yield self._parse_stream_chunk(chunk)

    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a single streaming chunk.

        This base implementation handles the common OpenAI-compatible format.
        Subclasses can override for provider-specific variations.
        """
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            return StreamChunk()

        delta = choice.delta
        finish_reason = None

        if choice.finish_reason:
            finish_reason = self._map_finish_reason(choice.finish_reason)

        delta_content = delta.content if hasattr(delta, "content") else None

        # check for reasoning field (primary) then reasoning_content (fallback)
        delta_reasoning = getattr(delta, "reasoning", None) or getattr(
            delta, "reasoning_content", None
        )

        delta_tool_call = None
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            delta_tool_call = self._parse_tool_call_from_delta(delta.tool_calls[0])

        return StreamChunk(
            delta_content=delta_content,
            delta_reasoning=delta_reasoning,
            delta_tool_call=delta_tool_call,
            finish_reason=finish_reason,
        )

    def _parse_tool_call_from_delta(self, tc: Any) -> PartialToolCall:
        """Parse a tool call from a stream delta.

        This base implementation assumes OpenAI object format.
        Subclasses can override for providers that use different formats.

        Args:
            tc: The tool call delta from the stream.

        Returns:
            PartialToolCall with the parsed data.
        """
        return PartialToolCall(
            index=tc.index,
            id=tc.id if tc.id else None,
            name=tc.function.name if tc.function and tc.function.name else None,
            arguments_delta=tc.function.arguments if tc.function and tc.function.arguments else None,
        )
