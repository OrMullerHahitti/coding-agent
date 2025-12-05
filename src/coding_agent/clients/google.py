"""Google Gemini client implementation.

This client handles communication with the Google Gemini API and normalizes
responses to the unified format.

Google Gemini has unique requirements:
- Uses "parts" format for message content
- Tool calls use "function_call" in parts
- Tool results use "function_response" in parts
- System instruction is a separate parameter
- Role names: "user" and "model" (not "assistant")
"""

import os
from typing import Any, Iterator

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import (
    InvalidArgument,
    ResourceExhausted,
    Unauthenticated,
    ServiceUnavailable,
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


class GoogleClient(BaseLLMClient):
    """Google Gemini API client with unified response handling.

    This client properly handles multi-turn conversations with tool calls,
    fixing the previous implementation that dropped history.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-pro-latest",
    ):
        """Initialize the Google Gemini client.

        Args:
            api_key: Google API key. Defaults to GOOGLE_API_KEY env var.
            model: Model to use. Defaults to Gemini 1.5 Pro.
        """
        api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self.model_name = model

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from Google Gemini.

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
        system_instruction, converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools) if tools else None

        # Create model with tools and system instruction
        model_kwargs: dict[str, Any] = {"model_name": self.model_name}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction
        if converted_tools:
            model_kwargs["tools"] = converted_tools

        model = genai.GenerativeModel(**model_kwargs)

        try:
            # Use generate_content with full history (not chat which drops context)
            response = model.generate_content(
                converted_messages,
                stream=stream,
                generation_config=GenerationConfig(
                    max_output_tokens=4096,
                ),
            )

            if stream:
                return self._stream_response(response)
            return self._parse_response(response)

        except Unauthenticated as e:
            raise AuthenticationError(f"Google authentication failed: {e}") from e
        except ResourceExhausted as e:
            raise RateLimitError("Google rate limit exceeded") from e
        except ServiceUnavailable as e:
            raise ProviderUnavailableError(f"Google API unavailable: {e}") from e
        except InvalidArgument as e:
            raise InvalidResponseError(f"Invalid request to Google API: {e}") from e

    def _convert_messages(
        self, messages: list[UnifiedMessage]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert unified messages to Gemini format.

        Gemini requires:
        - System instruction as separate parameter
        - "user" and "model" roles (not "assistant")
        - Parts-based content with function_call/function_response

        Returns:
            Tuple of (system_instruction, converted_messages)
        """
        system_instruction = None
        converted = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content

            elif msg.role == MessageRole.USER:
                converted.append({
                    "role": "user",
                    "parts": [{"text": msg.content}],
                })

            elif msg.role == MessageRole.ASSISTANT:
                parts: list[dict[str, Any]] = []
                if msg.content:
                    parts.append({"text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append({
                            "function_call": {
                                "name": tc.name,
                                "args": tc.arguments,
                            }
                        })
                converted.append({"role": "model", "parts": parts})

            elif msg.role == MessageRole.TOOL:
                # Gemini expects function_response in a user turn
                converted.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": msg.name,
                            "response": {"result": msg.content},
                        }
                    }],
                })

        return system_instruction, converted

    def _convert_tools(self, tools: list[BaseTool]) -> list[dict[str, Any]]:
        """Convert tools to Gemini function declaration format."""
        declarations = []
        for tool in tools:
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })
        return declarations

    def _parse_response(self, response: Any) -> UnifiedResponse:
        """Parse Gemini response into unified format."""
        try:
            candidate = response.candidates[0]
            content = candidate.content

            tool_calls = []
            text_content = ""

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text_content += part.text
                elif hasattr(part, "function_call"):
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        id=f"call_{fc.name}_{len(tool_calls)}",  # Gemini doesn't provide IDs
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    ))

            # Map finish reason
            finish_reason = FinishReason.STOP
            if candidate.finish_reason:
                finish_map = {
                    1: FinishReason.STOP,      # STOP
                    2: FinishReason.LENGTH,    # MAX_TOKENS
                    3: FinishReason.STOP,      # SAFETY
                    4: FinishReason.STOP,      # RECITATION
                    5: FinishReason.STOP,      # OTHER
                }
                finish_reason = finish_map.get(candidate.finish_reason, FinishReason.STOP)

            # Check if we have function calls - that's tool_use
            if tool_calls:
                finish_reason = FinishReason.TOOL_USE

            # Get usage if available
            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = UsageStats(
                    prompt_tokens=response.usage_metadata.prompt_token_count,
                    completion_tokens=response.usage_metadata.candidates_token_count,
                    total_tokens=response.usage_metadata.total_token_count,
                )

            return UnifiedResponse(
                message=UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content=text_content if text_content else None,
                    tool_calls=tool_calls if tool_calls else None,
                ),
                finish_reason=finish_reason,
                usage=usage,
            )
        except Exception as e:
            raise InvalidResponseError(f"Failed to parse Google response: {e}") from e

    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a single streaming chunk from Gemini."""
        try:
            if not chunk.candidates:
                return StreamChunk()

            candidate = chunk.candidates[0]
            if not hasattr(candidate, "content") or not candidate.content.parts:
                return StreamChunk()

            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    return StreamChunk(delta_content=part.text)
                elif hasattr(part, "function_call"):
                    fc = part.function_call
                    return StreamChunk(
                        delta_tool_call=PartialToolCall(
                            index=0,
                            id=f"call_{fc.name}",
                            name=fc.name,
                            arguments_delta=str(dict(fc.args) if fc.args else {}),
                        )
                    )

            # Check for finish
            if candidate.finish_reason:
                return StreamChunk(finish_reason=FinishReason.STOP)

        except Exception:
            pass

        return StreamChunk()

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        for chunk in response:
            parsed = self._parse_stream_chunk(chunk)
            if parsed.delta_content or parsed.delta_tool_call or parsed.finish_reason:
                yield parsed
