"""Tools for multi-agent coordination.

This module provides tools that enable the supervisor agent to
delegate tasks to worker agents.
"""

from typing import TYPE_CHECKING, Any

from ..tools.base import BaseTool

if TYPE_CHECKING:
    from .worker import WorkerAgent


class DelegateTaskTool(BaseTool):
    """Tool for delegating tasks to worker agents.

    This tool allows the supervisor to assign specific tasks to
    specialized workers and receive their results.
    """

    def __init__(self, workers: dict[str, "WorkerAgent"], verbose: bool = False):
        """Initialize the delegation tool.

        Args:
            workers: Dictionary mapping worker names to worker instances.
            verbose: Whether workers should run in verbose mode.
        """
        self._workers = workers
        self._verbose = verbose

    @property
    def name(self) -> str:
        return "delegate_task"

    @property
    def description(self) -> str:
        worker_list = "\n".join(
            f"  - {name}: {worker.description}"
            for name, worker in self._workers.items()
        )
        return (
            "Delegate a task to a specialized worker agent. "
            "Use this tool to assign work to the most appropriate worker.\n\n"
            f"Available workers:\n{worker_list}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "worker": {
                    "type": "string",
                    "enum": list(self._workers.keys()),
                    "description": "The name of the worker to assign the task to.",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "A clear, specific task description for the worker. "
                        "Include all necessary context and requirements."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Optional additional context or background information "
                        "that might help the worker complete the task."
                    ),
                },
            },
            "required": ["worker", "task"],
        }

    def execute(self, worker: str, task: str, context: str | None = None) -> str:
        """Execute a task delegation.

        Args:
            worker: Name of the worker to delegate to.
            task: The task description.
            context: Optional additional context.

        Returns:
            The worker's result or an error message.
        """
        if worker not in self._workers:
            available = ", ".join(self._workers.keys())
            return f"Error: Unknown worker '{worker}'. Available workers: {available}"

        worker_agent = self._workers[worker]

        try:
            if context:
                result, _ = worker_agent.execute_with_history(
                    task, context=context, verbose=self._verbose
                )
            else:
                result = worker_agent.execute(task, verbose=self._verbose)

            return f"[{worker}] {result}"
        except Exception as e:
            return f"Error: Worker '{worker}' failed with: {e}"


class SynthesizeResultsTool(BaseTool):
    """Tool for synthesizing results from multiple workers.

    This tool helps the supervisor combine and summarize results
    from different workers into a coherent response.
    """

    @property
    def name(self) -> str:
        return "synthesize_results"

    @property
    def description(self) -> str:
        return (
            "Synthesize and combine results from multiple workers into a coherent "
            "final response. Use this after gathering results from different workers "
            "to create a unified answer for the user."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A concise summary of all worker results.",
                },
                "details": {
                    "type": "string",
                    "description": "Detailed synthesis of the work done.",
                },
                "next_steps": {
                    "type": "string",
                    "description": "Optional suggested next steps or follow-up actions.",
                },
            },
            "required": ["summary", "details"],
        }

    def execute(
        self,
        summary: str,
        details: str,
        next_steps: str | None = None,
    ) -> str:
        """Format the synthesized results.

        Args:
            summary: Concise summary of results.
            details: Detailed synthesis.
            next_steps: Optional next steps.

        Returns:
            Formatted synthesis result.
        """
        result = f"## Summary\n{summary}\n\n## Details\n{details}"
        if next_steps:
            result += f"\n\n## Next Steps\n{next_steps}"
        return result
