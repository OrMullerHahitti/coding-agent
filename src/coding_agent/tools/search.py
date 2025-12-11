import os
from typing import Any

from tavily import TavilyClient

from .base import BaseTool


class TavilySearchTool(BaseTool):
    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            # We don't raise error here to allow agent to start,
            # but execution will fail if key is missing.
            self.client = None
        else:
            self.client = TavilyClient(api_key=api_key)

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return (
            "Search the web for information using Tavily. "
            "Use this tool to find up-to-date information, documentation, or answers to questions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The search query."}},
            "required": ["query"],
        }

    def execute(self, query: str) -> Any:
        if not self.client:
            return "Error: TAVILY_API_KEY not found in environment variables."

        try:
            response = self.client.search(query=query, search_depth="basic")
            # Format the results for better readability
            results = response.get("results", [])
            if not results:
                return "No results found."

            formatted_results = []
            for result in results:
                title = result.get("title", "No Title")
                url = result.get("url", "No URL")
                content = result.get("content", "No Content")
                formatted_results.append(f"Title: {title}\nURL: {url}\nContent: {content}\n")

            return "\n---\n".join(formatted_results)
        except Exception as e:
            return f"Error executing search: {str(e)}"
