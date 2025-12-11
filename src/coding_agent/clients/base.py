"""Base class for LLM clients.

All LLM provider clients inherit from BaseLLMClient and implement
the normalization methods to convert between provider-specific formats
and the unified types.
"""

import functools
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterator, TypeVar

from ..exceptions import ProviderUnavailableError, RateLimitError
from ..logging import get_logger
from ..tools.base import BaseTool
from ..types import (
    StreamChunk,
    UnifiedMessage,
    UnifiedResponse,
)

logger = get_logger(__name__)

T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying API calls with exponential backoff.

    Retries on RateLimitError and ProviderUnavailableError. Other exceptions
    are raised immediately.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds between retries (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Whether to add random jitter to delay (default: True)

    Returns:
        Decorated function with retry logic.

    Example:
        @with_retry(max_retries=3, initial_delay=1.0)
        def make_api_call():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (RateLimitError, ProviderUnavailableError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.warning(
                            f"max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    # calculate delay with optional jitter
                    actual_delay = min(delay, max_delay)
                    if jitter:
                        actual_delay *= (0.5 + random.random())

                    logger.info(
                        f"retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {actual_delay:.1f}s: {e}"
                    )
                    time.sleep(actual_delay)
                    delay *= exponential_base

            # should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper
    return decorator


class BaseLLMClient(ABC):
    """Abstract base class for all LLM clients.

    Each client is responsible for:
    1. Converting UnifiedMessage list to provider format
    2. Converting tool schemas to provider format
    3. Making API calls
    4. Converting responses back to UnifiedResponse/StreamChunk

    The agent only interacts with unified types - all provider-specific
    handling is encapsulated within each client implementation.
    """

    def __init__(self, client_config: dict | None = None):
        """Initialize the client.
        Args:
            client_config: Optional dictionary of configuration parameters
                           (e.g. temperature, max_tokens, etc.)
        """
        self.client_config = client_config or {}

    @abstractmethod
    def generate(
        self,
        messages: list[UnifiedMessage],
        tools: list[BaseTool] | None = None,
        stream: bool = False,
    ) -> UnifiedResponse | Iterator[StreamChunk]:
        """Generate a response from the LLM.

        Args:
            messages: Conversation history in unified format
            tools: Optional list of tools available to the model
            stream: Whether to stream the response

        Returns:
            UnifiedResponse for non-streaming, Iterator[StreamChunk] for streaming
        """

    @abstractmethod
    def _convert_messages(self, messages: list[UnifiedMessage]) -> Any:
        """Convert unified messages to provider-specific format.

        Each provider has different message formats:
        - OpenAI/Together: list of dicts with role/content/tool_calls
        - Anthropic: system separated, content blocks for tools
        - Google: parts-based format with function_call/function_response

        Args:
            messages: List of UnifiedMessage objects

        Returns:
            Provider-specific message format
        """

    @abstractmethod
    def _convert_tools(self, tools: list[BaseTool]) -> list[dict[str, Any]]:
        """Convert tool definitions to provider-specific format.

        Each provider uses different tool schemas:
        - OpenAI/Together: {type: "function", function: {name, description, parameters}}
        - Anthropic: {name, description, input_schema}
        - Google: {name, description, parameters}

        Args:
            tools: List of BaseTool objects

        Returns:
            Provider-specific tool definitions
        """

    @abstractmethod
    def _parse_response(self, response: Any) -> UnifiedResponse:
        """Parse provider response into unified format.

        Args:
            response: Raw response from the provider API

        Returns:
            UnifiedResponse with normalized message and metadata
        """


    @abstractmethod
    def _parse_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Parse a streaming chunk into unified format.

        Args:
            chunk: Raw chunk from the provider stream

        Returns:
            StreamChunk with delta content/tool_call updates
        """

    def format_system_prompt(self, prompt: str, tools: list[BaseTool]) -> str:
        """Format the system prompt with tool descriptions.

        Args:
            prompt: The raw system prompt template
            tools: List of available tools

        Returns:
            Formatted system prompt
        """
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
        return prompt.format(tool_descriptions=tool_descriptions)
