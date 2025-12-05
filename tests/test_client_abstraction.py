import pytest
from unittest.mock import MagicMock
from coding_agent.clients.base import BaseLLMClient
from coding_agent.clients.together import TogetherClient
from coding_agent.clients.openai import OpenAIClient
from coding_agent.agent import CodingAgent

def test_together_client_is_instance_of_base():
    client = TogetherClient(api_key="fake")
    assert isinstance(client, BaseLLMClient)

def test_openai_client_is_instance_of_base():
    client = OpenAIClient(api_key="fake")
    assert isinstance(client, BaseLLMClient)

def test_agent_accepts_any_client():
    mock_client = MagicMock(spec=BaseLLMClient)
    agent = CodingAgent(mock_client, [])
    assert agent.client == mock_client
