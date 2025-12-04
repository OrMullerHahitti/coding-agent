import os
from typing import List, Dict, Any, Optional
from together import Together
from .base import BaseLLMClient

class TogetherClient(BaseLLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"):
        self.client = Together(api_key=api_key or os.environ.get("TOGETHER_API_KEY"))
        self.model = model

    def generate_response(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """
        Generate a response from the Together API.
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
        Format tools for Together API (OpenAI compatible).
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
