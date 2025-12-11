"""Coding Agent - A provider-agnostic autonomous coding agent.

This package provides a ReAct-based coding agent that supports multiple
LLM providers through a unified interface.
"""

from .agent import CodingAgent
from .exceptions import (
    AgentError,
    ClientError,
    InterruptRequested,
    SecurityError,
    ToolError,
)
from .types import (
    AgentRunResult,
    AgentState,
    FinishReason,
    InterruptInfo,
    MessageRole,
    StreamChunk,
    ToolCall,
    UnifiedMessage,
    UnifiedResponse,
)

__all__ = [
    # main agent
    "CodingAgent",
    # types
    "AgentRunResult",
    "AgentState",
    "FinishReason",
    "InterruptInfo",
    "MessageRole",
    "StreamChunk",
    "ToolCall",
    "UnifiedMessage",
    "UnifiedResponse",
    # exceptions
    "AgentError",
    "ClientError",
    "InterruptRequested",
    "SecurityError",
    "ToolError",
]
