"""Unified types for the coding agent.

These types provide a provider-agnostic interface for LLM interactions.
All clients convert their provider-specific formats to/from these types.
"""

from dataclasses import dataclass
from enum import Enum, auto
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
    reasoning_content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary representation."""
        result: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            result["content"] = self.content
        if self.reasoning_content is not None:
            result["reasoning_content"] = self.reasoning_content
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
    delta_reasoning: str | None = None
    delta_tool_call: PartialToolCall | None = None
    finish_reason: FinishReason | None = None


# Type alias for streaming responses
StreamIterator = Iterator[StreamChunk]


# ==================== agent state types ====================


class AgentState(Enum):
    """State of the agent execution."""
    RUNNING = auto()
    INTERRUPTED = auto()
    AWAITING_CONFIRMATION = auto()
    COMPLETED = auto()
    ERROR = auto()


@dataclass
class InterruptInfo:
    """Information about an interrupt requiring user input.

    Attributes:
        tool_name: Name of the tool that triggered the interrupt
        tool_call_id: ID of the tool call (for resumption)
        question: The question to ask the user
        context: Optional additional context
    """
    tool_name: str
    tool_call_id: str
    question: str
    context: dict[str, Any] | None = None


@dataclass
class ConfirmationInfo:
    """Information about a pending confirmation request.

    Attributes:
        tool_name: Name of the tool requiring confirmation
        tool_call_id: ID of the tool call (for resumption)
        message: Description of what will happen if confirmed
        operation: Type of operation (write, execute, run_code)
        arguments: The arguments that will be passed to the tool
    """
    tool_name: str
    tool_call_id: str
    message: str
    operation: str
    arguments: dict[str, Any]


@dataclass
class AgentRunResult:
    """Result of an agent run, which may be complete, interrupted, or awaiting confirmation.

    Attributes:
        state: Current state of the agent
        content: Final response content (if completed)
        interrupt: Interrupt information (if interrupted)
        confirmation: Confirmation information (if awaiting confirmation)
        error: Error message (if error state)
    """
    state: AgentState
    content: str | None = None
    interrupt: InterruptInfo | None = None
    confirmation: ConfirmationInfo | None = None
    error: str | None = None

    @property
    def is_interrupted(self) -> bool:
        """Check if the agent is waiting for user input."""
        return self.state == AgentState.INTERRUPTED

    @property
    def is_awaiting_confirmation(self) -> bool:
        """Check if the agent is waiting for user confirmation."""
        return self.state == AgentState.AWAITING_CONFIRMATION

    @property
    def is_completed(self) -> bool:
        """Check if the agent has completed its task."""
        return self.state == AgentState.COMPLETED

    @property
    def is_error(self) -> bool:
        """Check if the agent encountered an error."""
        return self.state == AgentState.ERROR
