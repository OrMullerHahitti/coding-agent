"""Pydantic models for API requests and responses."""

from typing import Any

from pydantic import BaseModel


class RunRequest(BaseModel):
    """Request to run the agent with a user message."""

    message: str
    stream: bool = False


class ResumeRequest(BaseModel):
    """Request to resume after an interrupt (ask_user)."""

    tool_call_id: str
    response: str


class ConfirmRequest(BaseModel):
    """Request to confirm or reject a dangerous operation."""

    tool_call_id: str
    confirmed: bool


class InterruptInfo(BaseModel):
    """Information about an interrupt requiring user input."""

    tool_name: str
    tool_call_id: str
    question: str
    context: dict[str, Any] | None = None


class ConfirmationInfo(BaseModel):
    """Information about a pending confirmation request."""

    tool_name: str
    tool_call_id: str
    message: str
    operation: str
    arguments: dict[str, Any]


class AgentResponse(BaseModel):
    """Response from the agent."""

    state: str  # "completed", "interrupted", "awaiting_confirmation", "error"
    content: str | None = None
    interrupt: InterruptInfo | None = None
    confirmation: ConfirmationInfo | None = None
    error: str | None = None


class StreamChunk(BaseModel):
    """A chunk of streaming response."""

    type: str  # "content", "reasoning", "tool_call", "done", "error"
    content: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
