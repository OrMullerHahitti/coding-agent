import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .base import BaseLLMClient

class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def generate_response(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """
        Generate a response from the OpenAI API.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            stream=stream,
        )
        return response

    def format_tools(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """
        Format tools for OpenAI API.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
