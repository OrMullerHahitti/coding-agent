"""Tests for Anthropic and Google clients."""

import pytest
from unittest.mock import MagicMock
from coding_agent.clients.base import BaseLLMClient
from coding_agent.clients.anthropic import AnthropicClient
from coding_agent.clients.google import GoogleClient
from coding_agent.tools.base import BaseTool


class MockTool(BaseTool):
    @property
    def name(self):
        return "mock_tool"

    @property
    def description(self):
        return "A mock tool"

    @property
    def parameters(self):
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs):
        return "executed"


def test_anthropic_client_is_instance_of_base():
    """Test that AnthropicClient inherits from BaseLLMClient."""
    client = AnthropicClient(api_key="fake")
    assert isinstance(client, BaseLLMClient)


def test_google_client_is_instance_of_base():
    """Test that GoogleClient inherits from BaseLLMClient."""
    client = GoogleClient(api_key="fake")
    assert isinstance(client, BaseLLMClient)


def test_anthropic_convert_tools():
    """Test Anthropic tool conversion produces correct format."""
    client = AnthropicClient(api_key="fake")
    tool = MockTool()
    formatted = client._convert_tools([tool])
    assert len(formatted) == 1
    assert "input_schema" in formatted[0]
    assert formatted[0]["name"] == "mock_tool"


def test_google_convert_tools():
    """Test Google tool conversion produces correct format."""
    client = GoogleClient(api_key="fake")
    tool = MockTool()
    formatted = client._convert_tools([tool])
    assert len(formatted) == 1
    assert formatted[0]["name"] == "mock_tool"
    assert "parameters" in formatted[0]
