from unittest.mock import MagicMock
from coding_agent.agent import CodingAgent
from coding_agent.tools.base import BaseTool
from typing import Dict, Any

class MockTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {"arg": {"type": "string"}}}

    def execute(self, arg: str) -> str:
        return f"Executed with {arg}"

def test_agent_initialization(mock_client):
    agent = CodingAgent(mock_client, [])
    assert agent.client == mock_client
    assert agent.tools == {}

def test_agent_tool_registration(mock_client):
    tool = MockTool()
    agent = CodingAgent(mock_client, [tool])
    assert "mock_tool" in agent.tools
    assert agent.tools["mock_tool"] == tool
