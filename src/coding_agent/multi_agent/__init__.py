"""Multi-agent system for collaborative task execution.

This module provides a Supervisor-Worker pattern for orchestrating
multiple specialized agents to accomplish complex tasks.

Architecture:
    SupervisorAgent
        |
        +-- analyzes task
        +-- delegates to workers via delegate_task tool
        +-- synthesizes results
        |
        v
    WorkerAgent(s)
        - coder: writes and modifies code
        - researcher: finds information via search
        - reviewer: analyzes code quality

Example usage:
    from coding_agent.multi_agent import (
        SupervisorAgent,
        create_coder_worker,
        create_researcher_worker,
    )
    from coding_agent.clients.factory import create_client

    # create clients (can be different models for different roles)
    supervisor_client = create_client("anthropic")  # smart model for coordination
    coder_client = create_client("together")  # coding-optimized model

    # create workers
    workers = {
        "coder": create_coder_worker(coder_client),
        "researcher": create_researcher_worker(supervisor_client),
    }

    # create supervisor
    supervisor = SupervisorAgent(supervisor_client, workers)

    # run a task
    result = supervisor.run("Help me build a todo app in Python")
"""

from .supervisor import SupervisorAgent, create_supervisor
from .tools import DelegateTaskTool, SynthesizeResultsTool
from .worker import WorkerAgent
from .workers import (
    create_coder_worker,
    create_researcher_worker,
    create_reviewer_worker,
)

__all__ = [
    # core classes
    "SupervisorAgent",
    "WorkerAgent",
    # tools
    "DelegateTaskTool",
    "SynthesizeResultsTool",
    # factory functions
    "create_supervisor",
    "create_coder_worker",
    "create_researcher_worker",
    "create_reviewer_worker",
]
