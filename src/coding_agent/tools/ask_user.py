"""Human-in-the-loop tool for requesting user input."""

from typing import Any, Callable


# default callback uses input() for CLI usage
def default_input_callback(question: str) -> str:
    """Default callback that uses stdin input."""
    print(f"\n[Agent needs input]: {question}")
    return input("Your answer: ")


class AskUserTool:
    """Tool that allows the agent to ask the user for clarification.
    
    The input callback can be customized for different deployment scenarios:
    - CLI: Use the default `input()` based callback
    - Web: Provide a callback that sends a websocket message and waits for response
    - API: Provide a callback that queues the question and polls for answer
    """

    def __init__(self, input_callback: Callable[[str], str] | None = None):
        """Initialize the tool with an optional custom input callback.
        
        Args:
            input_callback: A function that takes a question string and returns
                           the user's response. Defaults to stdin input().
        """
        self._input_callback = input_callback or default_input_callback

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return (
            "Ask the user for clarification or additional information. "
            "Use this tool when you need more details to complete a task, "
            "when the user's request is ambiguous, or when you want to confirm "
            "an action before proceeding."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user. Be clear and specific.",
                },
            },
            "required": ["question"],
        }

    def execute(self, question: str) -> str:
        """Ask the user a question and return their response.

        Args:
            question: The question to ask the user.

        Returns:
            The user's response.
        """
        return self._input_callback(question)
