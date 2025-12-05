import pytest
from unittest.mock import MagicMock, patch
from coding_agent.tools.search import TavilySearchTool

@patch("coding_agent.tools.search.TavilyClient")
@patch.dict("os.environ", {"TAVILY_API_KEY": "fake_key"})
def test_tavily_search_tool_init(mock_tavily_client):
    tool = TavilySearchTool()
    assert tool.name == "search_web"
    assert tool.client is not None
    mock_tavily_client.assert_called_with(api_key="fake_key")

@patch.dict("os.environ", {}, clear=True)
def test_tavily_search_tool_no_key():
    tool = TavilySearchTool()
    assert tool.client is None

@patch("coding_agent.tools.search.TavilyClient")
@patch.dict("os.environ", {"TAVILY_API_KEY": "fake_key"})
def test_tavily_search_tool_execute(mock_tavily_client):
    mock_instance = mock_tavily_client.return_value
    mock_instance.search.return_value = {
        "results": [
            {"title": "Test Title", "url": "http://test.com", "content": "Test Content"}
        ]
    }
    
    tool = TavilySearchTool()
    result = tool.execute(query="test query")
    
    assert "Test Title" in result
    assert "http://test.com" in result
    assert "Test Content" in result
    mock_instance.search.assert_called_with(query="test query", search_depth="basic")

@patch("coding_agent.tools.search.TavilyClient")
@patch.dict("os.environ", {"TAVILY_API_KEY": "fake_key"})
def test_tavily_search_tool_execute_no_results(mock_tavily_client):
    mock_instance = mock_tavily_client.return_value
    mock_instance.search.return_value = {"results": []}
    
    tool = TavilySearchTool()
    result = tool.execute(query="test query")
    
    assert result == "No results found."
