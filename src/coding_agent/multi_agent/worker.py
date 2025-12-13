"""Worker agent for multi-agent system.

Workers are specialized agents that execute specific types of tasks
delegated by the supervisor.
"""

from ..agent import CodingAgent
from ..clients.base import BaseLLMClient
from ..tools.base import BaseTool
from ..types import AgentRunResult, AgentState


class WorkerAgent:
    """A specialized agent for executing delegated tasks.

    Workers are created with specific tools and prompts tailored for
    their role (e.g., coder, researcher, reviewer). They execute tasks
    assigned by the supervisor and return results.
    """

    def __init__(
        self,
        name: str,
        client: BaseLLMClient,
        tools: list[BaseTool],
        system_prompt: str,
        description: str = "",
        interactive: bool = False,
    ):
        """Initialize a worker agent.

        Args:
            name: Unique identifier for this worker (e.g., "coder", "researcher").
            client: The LLM client for this worker.
            tools: List of tools available to this worker.
            system_prompt: System prompt defining the worker's role and behavior.
            description: Human-readable description for the supervisor.
        """
        self.name = name
        self.description = description or f"Worker agent: {name}"
        self._client = client
        self._tools = tools
        self._system_prompt = system_prompt
        self._interactive = interactive

        # create the underlying agent
        self._agent = CodingAgent(
            client=client,
            tools=tools,
            system_prompt=system_prompt,
        )

    def execute(self, task: str, verbose: bool = False) -> str:
        """Execute a task and return the result.

        Args:
            task: The task description to execute.
            verbose: Whether to print verbose output.

        Returns:
            The result of the task execution as a string.
        """
        result = self._agent.run(task, stream=False, verbose=verbose)

        while True:
            if result.state == AgentState.COMPLETED:
                return result.content or "Task completed with no output."

            if result.state == AgentState.ERROR:
                return f"Error: {result.error}"

            if result.state == AgentState.INTERRUPTED:
                if not self._interactive:
                    return f"Worker interrupted: {result.interrupt.question if result.interrupt else 'Unknown'}"
                if not result.interrupt:
                    return "Worker interrupted: Unknown"
                try:
                    user_response = input(
                        f"\n[{self.name} asks]: {result.interrupt.question}\nYour answer: "
                    )
                except (KeyboardInterrupt, EOFError):
                    return "Worker interrupted: user cancelled input."
                result = self._agent.resume(
                    result.interrupt.tool_call_id,
                    user_response,
                    stream=False,
                    verbose=verbose,
                )
                continue

            if result.state == AgentState.AWAITING_CONFIRMATION:
                if not self._interactive:
                    return (
                        f"Worker needs confirmation: {result.confirmation.message if result.confirmation else 'Unknown'}"
                    )
                if not result.confirmation:
                    return "Worker needs confirmation: Unknown"
                try:
                    confirm = input(
                        f"\n[{self.name} confirm]: {result.confirmation.message} (y/n): "
                    ).strip().lower()
                except (KeyboardInterrupt, EOFError):
                    confirm = "n"
                result = self._agent.resume_confirmation(
                    result.confirmation.tool_call_id,
                    confirmed=(confirm == "y"),
                    stream=False,
                    verbose=verbose,
                )
                continue

            return f"Unexpected state: {result.state}"

    def execute_with_history(
        self,
        task: str,
        context: str | None = None,
        verbose: bool = False,
    ) -> tuple[str, list[dict]]:
        """Execute a task and return both result and conversation history.

        Useful when the supervisor needs to see the worker's reasoning.

        Args:
            task: The task description to execute.
            context: Optional additional context to prepend to the task.
            verbose: Whether to print verbose output.

        Returns:
            Tuple of (result_string, conversation_history).
        """
        full_task = f"{context}\n\n{task}" if context else task
        result = self.execute(full_task, verbose=verbose)
        history = self._agent.get_history()
        return result, history

    def clear_history(self) -> None:
        """Clear the worker's conversation history."""
        self._agent.clear_history()

    def get_history(self) -> list[dict]:
        """Get the worker's conversation history."""
        return self._agent.get_history()

    @property
    def tools(self) -> list[BaseTool]:
        """Get the list of tools available to this worker."""
        return self._tools

    def __repr__(self) -> str:
        return f"WorkerAgent(name='{self.name}', tools={len(self._tools)})"
