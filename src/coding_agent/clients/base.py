from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseLLMClient(ABC):
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, stream: bool = False) -> Any:
        """
        Generate a response from the LLM provider.
        """
        pass

    @abstractmethod
    def format_tools(self, tools: List[Any]) -> List[Dict[str, Any]]:
        """
        Format tools into the schema expected by the LLM provider.
        """
        pass
