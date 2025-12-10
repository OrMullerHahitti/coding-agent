"""Google Gemini client implementation using the new google-genai SDK.

This client handles communication with the Google Gemini API and normalizes
responses to the unified format.

Google Gemini has unique requirements:
- Uses "parts" format for message content
- Tool calls use "function_call" in parts
- Tool results use "function_response" in parts
- System instruction is a separate parameter
- Role names: "user" and "model" (not "assistant")
- Supports thinking/reasoning with thinking_budget and include_thoughts

Supported models:
- gemini-2.0-flash (recommended)
- gemini-2.5-pro-preview
- gemini-2.5-flash-preview
"""

import os
from typing import Any, Iterator

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError

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

# supported configuration keys for google
SUPPORTED_CONFIG_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "max_tokens",
    "stop_sequences",
    # thinking features
    "thinking_budget",
    "thinking_level",
    "include_thoughts",
    # function calling
    "function_calling_mode",
}


class GoogleClient(BaseLLMClient):
    """Google Gemini API client using the new google-genai SDK.

    Supports:
    - Thinking/reasoning with thinking_budget configuration
    - Generation parameters: temperature, top_p, top_k, max_tokens
    - Function calling modes: AUTO, ANY, NONE
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        client_config: dict | None = None,
    ):
        """Initialize the Google client.

        Args:
            api_key: Google API key. Defaults to GOOGLE_API_KEY or GEMINI_API_KEY env var.
            model: Model to use. Defaults to gemini-2.0-flash.
            client_config: Optional configuration parameters:
                - temperature: float (default 1.0 for Gemini 3)
                - top_p: float (default 0.95)
                - top_k: int
                - max_tokens: int (default 4096)
                - stop_sequences: list[str]
                - thinking_budget: int (0-24576 for Flash, 128-32768 for Pro)
                - thinking_level: str ("low" or "high" for Gemini 3 Pro)
                - include_thoughts: bool (return thought summaries)
                - function_calling_mode: str ("AUTO", "ANY", "NONE")
        """
        super().__init__(client_config)

        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise ValueError("Google API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY env var.")

        self.client = genai.Client(api_key=resolved_key)
        self.model_name = model
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the client configuration."""
        if not self.client_config:
            return

        unsupported = set(self.client_config.keys()) - SUPPORTED_CONFIG_KEYS
        if unsupported:
            raise ValueError(f"Unsupported config keys for Google: {unsupported}")

        mode = self.client_config.get("function_calling_mode")
        if mode and mode not in ("AUTO", "ANY", "NONE"):
            raise ValueError(f"Invalid function_calling_mode: {mode}. Must be AUTO, ANY, or NONE.")

        level = self.client_config.get("thinking_level")
        if level and level not in ("low", "high"):
            raise ValueError(f"Invalid thinking_level: {level}. Must be 'low' or 'high'.")

    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from Google Gemini."""
        system_instruction, converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools) if tools else None

        config = self._build_generation_config(converted_tools, system_instruction)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=converted_messages,
                config=config,
            )

            if stream:
                return self._stream_response(response)
            return self._parse_response(response)

        except ClientError as e:
            error_msg = str(e).lower()
            if "unauthorized" in error_msg or "authentication" in error_msg or "api key" in error_msg:
                raise AuthenticationError(f"Google authentication failed: {e}") from e
            raise InvalidResponseError(f"Invalid request to Google API: {e}") from e
        except ServerError as e:
            error_msg = str(e).lower()
            if "rate" in error_msg or "quota" in error_msg or "resource" in error_msg:
                raise RateLimitError("Google rate limit exceeded") from e
            raise ProviderUnavailableError(f"Google API unavailable: {e}") from e
        except APIError as e:
            raise InvalidResponseError(f"Google API error: {e}") from e

    def _build_generation_config(
        self,
        tools: list[dict[str, Any]] | None,
        system_instruction: str | None = None,
    ) -> types.GenerateContentConfig:
        """Build the generation config from client configuration."""
        cfg = self.client_config or {}

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": cfg.get("max_tokens", 4096),
        }

        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        if "temperature" in cfg:
            config_kwargs["temperature"] = cfg["temperature"]
        if "top_p" in cfg:
            config_kwargs["top_p"] = cfg["top_p"]
        if "top_k" in cfg:
            config_kwargs["top_k"] = cfg["top_k"]
        if "stop_sequences" in cfg:
            config_kwargs["stop_sequences"] = cfg["stop_sequences"]

        thinking_budget = cfg.get("thinking_budget")
        thinking_level = cfg.get("thinking_level")
        include_thoughts = cfg.get("include_thoughts", False)

        if thinking_budget is not None or thinking_level or include_thoughts:
            thinking_config_kwargs: dict[str, Any] = {}
            if thinking_budget is not None:
                thinking_config_kwargs["thinking_budget"] = thinking_budget
            if thinking_level:
                thinking_config_kwargs["thinking_level"] = thinking_level
            if include_thoughts:
                thinking_config_kwargs["include_thoughts"] = include_thoughts
            config_kwargs["thinking_config"] = types.ThinkingConfig(**thinking_config_kwargs)

        if tools:
            config_kwargs["tools"] = [types.Tool(function_declarations=tools)]
            mode = cfg.get("function_calling_mode", "AUTO")
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=mode)
            )

        return types.GenerateContentConfig(**config_kwargs)

    def _convert_messages(
        self, messages: list[UnifiedMessage]
    ) -> tuple[str | None, list[types.Content]]:
        """Convert unified messages to Gemini format."""
        system_instruction = None
        converted: list[types.Content] = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content

            elif msg.role == MessageRole.USER:
                converted.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content or "")],
                ))

            elif msg.role == MessageRole.ASSISTANT:
                parts: list[types.Part] = []
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(types.Part.from_function_call(
                            name=tc.name,
                            args=tc.arguments,
                        ))
                converted.append(types.Content(role="model", parts=parts))

            elif msg.role == MessageRole.TOOL:
                converted.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=msg.name or "",
                        response={"result": msg.content},
                    )],
                ))

        return system_instruction, converted

    def _convert_tools(self, tools: list[BaseTool]) -> list[types.FunctionDeclaration]:
        """Convert tools to Gemini function declaration format."""
        declarations = []
        for tool in tools:
            declarations.append(types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            ))
        return declarations

    def _parse_response(self, response: Any) -> UnifiedResponse:
        """Parse Gemini response into unified format."""
        try:
            candidate = response.candidates[0]
            content = candidate.content

            tool_calls = []
            text_content = ""
            reasoning_content = ""

            for part in content.parts:
                if hasattr(part, "thought") and part.thought:
                    reasoning_content += part.text if hasattr(part, "text") else ""
                elif hasattr(part, "text") and part.text:
                    text_content += part.text
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        id=f"call_{fc.name}_{len(tool_calls)}",
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    ))

            finish_reason = FinishReason.STOP
            if candidate.finish_reason:
                finish_map = {
                    "STOP": FinishReason.STOP,
                    "MAX_TOKENS": FinishReason.LENGTH,
                    "SAFETY": FinishReason.STOP,
                    "RECITATION": FinishReason.STOP,
                    "OTHER": FinishReason.STOP,
                }
                finish_reason = finish_map.get(str(candidate.finish_reason), FinishReason.STOP)

            if tool_calls:
                finish_reason = FinishReason.TOOL_USE

            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage = UsageStats(
                    prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                    completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
                    total_tokens=getattr(um, "total_token_count", 0) or 0,
                )

            return UnifiedResponse(
                message=UnifiedMessage(
                    role=MessageRole.ASSISTANT,
                    content=text_content if text_content else None,
                    reasoning_content=reasoning_content if reasoning_content else None,
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
                if hasattr(part, "thought") and part.thought:
                    return StreamChunk(delta_reasoning=part.text if hasattr(part, "text") else "")
                elif hasattr(part, "text") and part.text:
                    return StreamChunk(delta_content=part.text)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    return StreamChunk(
                        delta_tool_call=PartialToolCall(
                            index=0,
                            id=f"call_{fc.name}",
                            name=fc.name,
                            arguments_delta=str(dict(fc.args) if fc.args else {}),
                        )
                    )

            if candidate.finish_reason:
                return StreamChunk(finish_reason=FinishReason.STOP)

        except Exception:
            pass

        return StreamChunk()

    def _stream_response(self, response: Any) -> Iterator[StreamChunk]:
        """Stream response as StreamChunk iterator."""
        for chunk in response:
            parsed = self._parse_stream_chunk(chunk)
            if (parsed.delta_content or parsed.delta_reasoning or
                    parsed.delta_tool_call or parsed.finish_reason):
                yield parsed
