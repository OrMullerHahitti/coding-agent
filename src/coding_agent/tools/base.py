from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all tools.

    Tools that perform dangerous operations (file writes, command execution,
    code execution) should set REQUIRES_CONFIRMATION = True and provide a
    CONFIRMATION_MESSAGE template.
    """

    # confirmation configuration - override in subclasses for dangerous tools
    REQUIRES_CONFIRMATION: bool = False
    CONFIRMATION_MESSAGE: str = ""
    OPERATION_TYPE: str = ""  # e.g., "write", "execute", "run_code"
    CONFIRMATION_CHECK_ARG: str = "path"  # argument name used for auto-approve pattern matching

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

    def get_confirmation_message(self, **kwargs) -> str:
        """Format the confirmation message with the given arguments.

        Override this method for more complex confirmation messages.

        Args:
            **kwargs: The arguments that will be passed to execute()

        Returns:
            Formatted confirmation message
        """
        if not self.CONFIRMATION_MESSAGE:
            return f"Execute {self.name} with args: {kwargs}"

        try:
            # add computed values for templates
            format_args = dict(kwargs)
            if "content" in kwargs:
                format_args["len_content"] = len(kwargs["content"])
            if "code" in kwargs:
                format_args["len_code"] = len(kwargs["code"])
            return self.CONFIRMATION_MESSAGE.format(**format_args)
        except KeyError:
            # fallback if template has missing keys
            return f"Execute {self.name} with args: {kwargs}"

    def to_schema(self) -> dict[str, Any]:
        """Return the tool schema for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
