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

        # handle different result states
        if result.state == AgentState.COMPLETED:
            return result.content or "Task completed with no output."

        if result.state == AgentState.ERROR:
            return f"Error: {result.error}"

        if result.state == AgentState.INTERRUPTED:
            # workers shouldn't use interrupt tools, but handle gracefully
            return f"Worker interrupted: {result.interrupt.question if result.interrupt else 'Unknown'}"

        if result.state == AgentState.AWAITING_CONFIRMATION:
            # workers shouldn't need confirmation in autonomous mode
            return f"Worker needs confirmation: {result.confirmation.message if result.confirmation else 'Unknown'}"

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
