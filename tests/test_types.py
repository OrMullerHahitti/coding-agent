"""Tests for unified types."""

import pytest

from coding_agent.types import (
    MessageRole,
    FinishReason,
    ToolCall,
    PartialToolCall,
    UsageStats,
    UnifiedMessage,
    UnifiedResponse,
    StreamChunk,
)


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_enum_values(self):
        """Test that enum has expected values."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.TOOL.value == "tool"


class TestFinishReason:
    """Tests for FinishReason enum."""

    def test_enum_values(self):
        """Test that enum has expected values."""
        assert FinishReason.STOP.value == "stop"
        assert FinishReason.TOOL_USE.value == "tool_use"
        assert FinishReason.LENGTH.value == "length"
        assert FinishReason.ERROR.value == "error"


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_creation(self):
        """Test creating a tool call."""
        tc = ToolCall(
            id="call_123",
            name="calculator",
            arguments={"a": 1, "b": 2},
        )
        assert tc.id == "call_123"
        assert tc.name == "calculator"
        assert tc.arguments == {"a": 1, "b": 2}


class TestUnifiedMessage:
    """Tests for UnifiedMessage dataclass."""

    def test_simple_message(self):
        """Test creating a simple message."""
        msg = UnifiedMessage(
            role=MessageRole.USER,
            content="Hello!",
        )
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_assistant_with_tool_calls(self):
        """Test assistant message with tool calls."""
        tc = ToolCall(id="1", name="calc", arguments={})
        msg = UnifiedMessage(
            role=MessageRole.ASSISTANT,
            content="Let me calculate that.",
            tool_calls=[tc],
        )
        assert msg.tool_calls == [tc]

    def test_tool_result_message(self):
        """Test tool result message."""
        msg = UnifiedMessage(
            role=MessageRole.TOOL,
            content="42",
            tool_call_id="call_123",
            name="calculator",
        )
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_123"
        assert msg.name == "calculator"

    def test_to_dict_simple(self):
        """Test converting simple message to dict."""
        msg = UnifiedMessage(
            role=MessageRole.USER,
            content="Hello!",
        )
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello!"
        assert "tool_calls" not in d

    def test_to_dict_with_tool_calls(self):
        """Test converting message with tool calls to dict."""
        tc = ToolCall(id="1", name="calc", arguments={"x": 1})
        msg = UnifiedMessage(
            role=MessageRole.ASSISTANT,
            tool_calls=[tc],
        )
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["name"] == "calc"


class TestUnifiedResponse:
    """Tests for UnifiedResponse dataclass."""

    def test_creation(self):
        """Test creating a response."""
        msg = UnifiedMessage(role=MessageRole.ASSISTANT, content="Hi!")
        usage = UsageStats(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        resp = UnifiedResponse(
            message=msg,
            finish_reason=FinishReason.STOP,
            usage=usage,
        )
        assert resp.message == msg
        assert resp.finish_reason == FinishReason.STOP
        assert resp.usage.total_tokens == 15

    def test_tool_use_response(self):
        """Test response with tool use."""
        tc = ToolCall(id="1", name="calc", arguments={})
        msg = UnifiedMessage(role=MessageRole.ASSISTANT, tool_calls=[tc])
        resp = UnifiedResponse(
            message=msg,
            finish_reason=FinishReason.TOOL_USE,
        )
        assert resp.finish_reason == FinishReason.TOOL_USE


class TestStreamChunk:
    """Tests for StreamChunk dataclass."""

    def test_text_chunk(self):
        """Test text content chunk."""
        chunk = StreamChunk(delta_content="Hello")
        assert chunk.delta_content == "Hello"
        assert chunk.delta_tool_call is None
        assert chunk.finish_reason is None

    def test_tool_call_chunk(self):
        """Test tool call chunk."""
        tc = PartialToolCall(index=0, name="calc")
        chunk = StreamChunk(delta_tool_call=tc)
        assert chunk.delta_tool_call == tc

    def test_finish_chunk(self):
        """Test finish chunk."""
        chunk = StreamChunk(finish_reason=FinishReason.STOP)
        assert chunk.finish_reason == FinishReason.STOP
