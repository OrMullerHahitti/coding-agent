"""Human-in-the-loop tool for requesting user input.

This tool supports two modes:
1. Interrupt mode (default): Raises InterruptRequested for framework-agnostic handling
2. Callback mode: Uses a provided callback for synchronous environments (CLI)
"""

from typing import Any, Callable

from ..exceptions import InterruptRequested
from .base import BaseTool


class AskUserTool(BaseTool):
    """Tool that allows the agent to ask the user for clarification.

    The tool supports two operational modes:

    1. **Interrupt Mode** (default, `use_interrupt=True`):
       - Raises `InterruptRequested` exception when executed
       - Agent loop catches this and returns control to the caller
       - Caller provides the response and resumes the agent
       - Works in any environment: CLI, web, API, async frameworks

    2. **Callback Mode** (`use_interrupt=False`):
       - Uses a provided callback function to get user input
       - Blocks until user responds
       - Simple for CLI applications but not suitable for web/API

    Example (Interrupt Mode):
        ```python
        tool = AskUserTool(use_interrupt=True)
        agent = CodingAgent(client, [tool])

        result = agent.run("help me with something")
        if result.is_interrupted:
            user_response = get_user_input(result.interrupt.question)
            result = agent.resume(result.interrupt.tool_call_id, user_response)
        ```

    Example (Callback Mode):
        ```python
        tool = AskUserTool(use_interrupt=False, input_callback=my_input_func)
        agent = CodingAgent(client, [tool])
        result = agent.run("help me with something")  # blocks for input
        ```
    """

    # sentinel value to identify this as an interrupt-capable tool
    INTERRUPT_TOOL = True

    def __init__(
        self,
        use_interrupt: bool = True,
        input_callback: Callable[[str], str] | None = None,
    ):
        """Initialize the tool.

        Args:
            use_interrupt: If True, raises InterruptRequested instead of blocking.
                          If False, uses the callback for synchronous input.
            input_callback: Callback for synchronous mode. If not provided and
                           use_interrupt=False, uses default stdin callback.
        """
        self.use_interrupt = use_interrupt
        self._input_callback = input_callback

        if not use_interrupt and not input_callback:
            # provide default CLI callback for backward compatibility
            self._input_callback = self._default_input_callback

    @staticmethod
    def _default_input_callback(question: str) -> str:
        """Default callback that uses stdin input."""
        print(f"\n[Agent needs input]: {question}")
        return input("Your answer: ")

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

    def execute(self, question: str, _tool_call_id: str = "") -> str:
        """Ask the user a question.

        Args:
            question: The question to ask the user.
            _tool_call_id: Internal parameter passed by agent for interrupt handling.

        Returns:
            The user's response (callback mode only).

        Raises:
            InterruptRequested: When in interrupt mode, signals that user input is needed.
        """
        if self.use_interrupt:
            raise InterruptRequested(
                tool_name=self.name,
                tool_call_id=_tool_call_id,
                question=question,
            )

        return self._input_callback(question)
