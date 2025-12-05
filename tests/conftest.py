"""Shared test fixtures and configuration."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from coding_agent.clients.base import BaseLLMClient
from coding_agent.types import (
    UnifiedMessage,
    UnifiedResponse,
    MessageRole,
    FinishReason,
    ToolCall,
    UsageStats,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for file tests."""
    return tmp_path


@pytest.fixture
def mock_client():
    """Create a mock LLM client."""
    client = MagicMock(spec=BaseLLMClient)
    return client


@pytest.fixture
def sample_messages():
    """Create sample conversation messages."""
    return [
        UnifiedMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        UnifiedMessage(role=MessageRole.USER, content="Hello!"),
        UnifiedMessage(role=MessageRole.ASSISTANT, content="Hi there!"),
    ]


@pytest.fixture
def sample_tool_call():
    """Create a sample tool call."""
    return ToolCall(
        id="call_123",
        name="calculator",
        arguments={"a": 1, "b": 2, "operation": "add"},
    )


@pytest.fixture
def sample_response():
    """Create a sample unified response."""
    return UnifiedResponse(
        message=UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content="The result is 3.",
        ),
        finish_reason=FinishReason.STOP,
        usage=UsageStats(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )
