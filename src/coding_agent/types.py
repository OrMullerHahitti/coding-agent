"""Unified types for the coding agent.

These types provide a provider-agnostic interface for LLM interactions.
All clients convert their provider-specific formats to/from these types.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator


class MessageRole(Enum):
    """Role of a message in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(Enum):
    """Reason why the model stopped generating."""
    STOP = "stop"
    TOOL_USE = "tool_use"
    LENGTH = "length"
    ERROR = "error"


@dataclass
class ToolCall:
    """A tool call requested by the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class PartialToolCall:
    """A partial tool call during streaming."""
    index: int
    id: str | None = None
    name: str | None = None
    arguments_delta: str | None = None


@dataclass
class UsageStats:
    """Token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class UnifiedMessage:
    """A message in the conversation history.

    This is the canonical message format used throughout the agent.
    Each LLM client converts to/from this format internally.

    Attributes:
        role: The role of the message sender
        content: Text content of the message (optional for tool calls)
        tool_calls: List of tool calls (only for assistant messages)
        tool_call_id: ID of the tool call this message responds to (only for tool role)
        name: Name of the tool (only for tool role)
    """
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary representation."""
        result: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls:
            result["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ]
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            result["name"] = self.name
        return result


@dataclass
class UnifiedResponse:
    """Response from an LLM provider.

    This wraps the model's response in a provider-agnostic format.

    Attributes:
        message: The assistant's response message
        finish_reason: Why the model stopped generating
        usage: Token usage statistics (optional)
    """
    message: UnifiedMessage
    finish_reason: FinishReason
    usage: UsageStats | None = None


@dataclass
class StreamChunk:
    """A chunk of a streaming response.

    Attributes:
        delta_content: New text content in this chunk
        delta_tool_call: Partial tool call update
        finish_reason: Set on the final chunk
    """
    delta_content: str | None = None
    delta_tool_call: PartialToolCall | None = None
    finish_reason: FinishReason | None = None


# Type alias for streaming responses
StreamIterator = Iterator[StreamChunk]
