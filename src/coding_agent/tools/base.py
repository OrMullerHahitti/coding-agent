from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """Return the JSON schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute the tool with the given arguments."""
        pass

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
