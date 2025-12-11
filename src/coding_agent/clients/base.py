"""Base class for LLM clients.

All LLM provider clients inherit from BaseLLMClient and implement
the normalization methods to convert between provider-specific formats
and the unified types.
"""

from abc import ABC, abstractmethod
from typing import Any, Iterator

from ..tools.base import BaseTool
from ..types import (
    StreamChunk,
    UnifiedMessage,
    UnifiedResponse,
)


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
