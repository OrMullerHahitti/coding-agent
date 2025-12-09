"""OpenAI client implementation.

This client handles communication with the OpenAI API and normalizes
responses to the unified format.
"""

import os
from contextlib import contextmanager
from typing import Any

from openai import APIConnectionError, OpenAI
from openai import AuthenticationError as OpenAIAuthError
from openai import RateLimitError as OpenAIRateLimitError

from ..exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)
from ..types import PartialToolCall, StreamChunk
from .openai_compat import OpenAICompatibleClient


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI API client with unified response handling."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        client_config: dict | None = None,
    ):
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            model: Model to use. Defaults to gpt-4o.
            client_config: Optional dictionary of configuration parameters.
        """
        super().__init__(api_key, model, client_config)

    def _create_client(self, api_key: str | None) -> OpenAI:
        """Create the OpenAI SDK client."""
        return OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def _get_supported_config_keys(self) -> set[str]:
        """Return config keys supported by OpenAI."""
        return {
            "temperature",
            "top_p",
            "top_k",
            "repetition_penalty",
            "max_tokens",
            "stop",
            "reasoning_effort",
            "presence_penalty",
            "frequency_penalty",
        }

    def _get_default_api_args(self) -> dict[str, Any]:
        """Return default API arguments for OpenAI."""
        return {}  # OpenAI uses API defaults

    @contextmanager
    def _handle_api_errors(self):
        """Handle OpenAI-specific errors."""
        try:
            yield
        except OpenAIAuthError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}") from e
        except OpenAIRateLimitError as e:
            raise RateLimitError("OpenAI rate limit exceeded") from e
        except APIConnectionError as e:
            raise ProviderUnavailableError(f"OpenAI API unavailable: {e}") from e

    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a single streaming chunk from OpenAI."""
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
            tc = delta.tool_calls[0]
            delta_tool_call = PartialToolCall(
                index=tc.index,
                id=tc.id if tc.id else None,
                name=tc.function.name if tc.function and tc.function.name else None,
                arguments_delta=tc.function.arguments if tc.function and tc.function.arguments else None,
            )

        return StreamChunk(
            delta_content=delta_content,
            delta_reasoning=delta_reasoning,
            delta_tool_call=delta_tool_call,
            finish_reason=finish_reason,
        )
