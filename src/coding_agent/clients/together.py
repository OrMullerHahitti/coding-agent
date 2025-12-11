"""Together AI client implementation.

Together AI provides an OpenAI-compatible API, so this client
extends OpenAICompatibleClient with Together-specific handling.
"""

import os
from contextlib import contextmanager
from typing import Any

from together import Together
from together.error import AuthenticationError as TogetherAuthError
from together.error import RateLimitError as TogetherRateLimitError

from ..exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)
from ..types import PartialToolCall
from .openai_compat import OpenAICompatibleClient


class TogetherClient(OpenAICompatibleClient):
    """Together AI client with unified response handling.

    Together AI uses an OpenAI-compatible API, supporting models like
    Meta-Llama, Mistral, and others.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        client_config: dict | None = None,
    ):
        """Initialize the Together client.

        Args:
            api_key: Together API key. Defaults to TOGETHER_API_KEY env var.
            model: Model to use. Defaults to Llama 3.1 70B.
            client_config: Optional dictionary of configuration parameters.
        """
        super().__init__(api_key, model, client_config)

    def _create_client(self, api_key: str | None) -> Together:
        """Create the Together SDK client."""
        return Together(api_key=api_key or os.environ.get("TOGETHER_API_KEY"))

    def _get_supported_config_keys(self) -> set[str]:
        """Return config keys supported by Together."""
        return {
            "temperature",
            "top_p",
            "top_k",
            "repetition_penalty",
            "max_tokens",
            "stop",
            "reasoning_effort",
        }

    def _get_default_api_args(self) -> dict[str, Any]:
        """Return default API arguments for Together."""
        return {"max_tokens": 4096}

    @contextmanager
    def _handle_api_errors(self):
        """Handle Together-specific errors."""
        try:
            yield
        except TogetherAuthError as e:
            raise AuthenticationError(f"Together authentication failed: {e}") from e
        except TogetherRateLimitError as e:
            raise RateLimitError("Together rate limit exceeded") from e
        except Exception as e:
            if "connection" in str(e).lower():
                raise ProviderUnavailableError(f"Together API unavailable: {e}") from e
            raise

    def _parse_tool_call_from_delta(self, tc: Any) -> PartialToolCall:
        """Parse a tool call from a stream delta.

        Together may return tool calls as dict or object, so we handle both.
        """
        # together may return dict or object - handle both formats
        if isinstance(tc, dict):
            index = tc.get("index")
            fn = tc.get("function", {})
            if isinstance(fn, dict):
                name = fn.get("name")
                arguments = fn.get("arguments")
            else:
                name = fn.name
                arguments = fn.arguments
            id_ = tc.get("id")
        else:
            index = tc.index
            id_ = tc.id
            name = tc.function.name if tc.function else None
            arguments = tc.function.arguments if tc.function else None

        return PartialToolCall(
            index=index,
            id=id_ if id_ else None,
            name=name if name else None,
            arguments_delta=arguments if arguments else None,
        )
