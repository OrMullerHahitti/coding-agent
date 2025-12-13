"""Supervisor agent for multi-agent orchestration.

The supervisor coordinates multiple worker agents to accomplish
complex tasks through delegation and result synthesis.
"""

from ..agent import CodingAgent
from ..clients.base import BaseLLMClient
from ..types import AgentRunResult, AgentState
from .prompts import format_supervisor_prompt
from .tools import DelegateTaskTool, SynthesizeResultsTool
from .worker import WorkerAgent


class SupervisorAgent:
    """Orchestrates multiple worker agents to accomplish tasks.

    The supervisor:
    1. Analyzes incoming tasks
    2. Delegates subtasks to appropriate workers
    3. Coordinates between workers when needed
    4. Synthesizes results into a final response
    """

    def __init__(
        self,
        client: BaseLLMClient,
        workers: dict[str, WorkerAgent],
        verbose: bool = False,
    ):
        """Initialize the supervisor agent.

        Args:
            client: LLM client for the supervisor (should be a capable model).
            workers: Dictionary mapping worker names to worker instances.
            verbose: Whether to run in verbose mode.
        """
        self.workers = workers
        self.verbose = verbose

        # build worker descriptions for the prompt
        worker_descriptions = "\n".join(
            f"- {name}: {worker.description}"
            for name, worker in workers.items()
        )

        # create delegation tools
        delegate_tool = DelegateTaskTool(workers, verbose=verbose)
        synthesize_tool = SynthesizeResultsTool()

        # create the underlying agent with delegation capabilities
        self._agent = CodingAgent(
            client=client,
            tools=[delegate_tool, synthesize_tool],
            system_prompt=format_supervisor_prompt(worker_descriptions),
        )

    def run(self, task: str, stream: bool = False) -> AgentRunResult:
        """Run the supervisor on a task.

        The supervisor will analyze the task, delegate to workers as needed,
        and synthesize the results.

        Args:
            task: The user's task or request.
            stream: Whether to stream the response.

        Returns:
            AgentRunResult with the final synthesized response.
        """
        return self._agent.run(task, stream=stream, verbose=self.verbose)

    def run_with_worker_history(self, task: str) -> tuple[AgentRunResult, dict[str, list[dict]]]:
        """Run the supervisor and return worker conversation histories.

        Useful for debugging or understanding how workers approached their tasks.

        Args:
            task: The user's task or request.

        Returns:
            Tuple of (result, worker_histories) where worker_histories maps
            worker names to their conversation histories.
        """
        result = self.run(task)

        worker_histories = {
            name: worker.get_history()
            for name, worker in self.workers.items()
        }

        return result, worker_histories

    def clear_all_histories(self) -> None:
        """Clear conversation histories for supervisor and all workers."""
        self._agent.clear_history()
        for worker in self.workers.values():
            worker.clear_history()

    def get_supervisor_history(self) -> list[dict]:
        """Get the supervisor's conversation history."""
        return self._agent.get_history()

    def add_worker(self, name: str, worker: WorkerAgent) -> None:
        """Add a new worker to the team.

        Note: This requires reinitializing the agent to update the tools.

        Args:
            name: The worker's name.
            worker: The worker instance.
        """
        self.workers[name] = worker
        # reinitialize the agent with updated workers
        self._reinitialize_agent()

    def remove_worker(self, name: str) -> bool:
        """Remove a worker from the team.

        Args:
            name: The worker's name.

        Returns:
            True if worker was removed, False if not found.
        """
        if name in self.workers:
            del self.workers[name]
            self._reinitialize_agent()
            return True
        return False

    def _reinitialize_agent(self) -> None:
        """Reinitialize the agent with current workers."""
        worker_descriptions = "\n".join(
            f"- {name}: {worker.description}"
            for name, worker in self.workers.items()
        )

        delegate_tool = DelegateTaskTool(self.workers, verbose=self.verbose)
        synthesize_tool = SynthesizeResultsTool()

        # preserve the client
        client = self._agent.client

        self._agent = CodingAgent(
            client=client,
            tools=[delegate_tool, synthesize_tool],
            system_prompt=format_supervisor_prompt(worker_descriptions),
        )


def create_supervisor(
    supervisor_client: BaseLLMClient,
    workers: dict[str, WorkerAgent],
    verbose: bool = False,
) -> SupervisorAgent:
    """Factory function to create a supervisor with workers.

    Args:
        supervisor_client: LLM client for the supervisor.
        workers: Dictionary of worker name to WorkerAgent.
        verbose: Whether to run in verbose mode.

    Returns:
        Configured SupervisorAgent.
    """
    return SupervisorAgent(
        client=supervisor_client,
        workers=workers,
        verbose=verbose,
    )
