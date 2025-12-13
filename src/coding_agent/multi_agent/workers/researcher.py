"""Researcher worker agent factory.

Creates a worker specialized for finding and synthesizing information.
"""

from ...clients.base import BaseLLMClient
from ...tools.filesystem import ListDirectoryTool, ReadFileTool
from ...tools.search import TavilySearchTool
from ..prompts import RESEARCHER_PROMPT
from ..worker import WorkerAgent


def create_researcher_worker(client: BaseLLMClient) -> WorkerAgent:
    """Create a researcher worker agent.

    The researcher worker is specialized for finding information through
    web searches and reading files. It synthesizes findings into clear summaries.

    Args:
        client: LLM client for the worker.

    Returns:
        Configured researcher WorkerAgent.
    """
    tools = [
        TavilySearchTool(),
        ReadFileTool(),
        ListDirectoryTool(),
    ]

    return WorkerAgent(
        name="researcher",
        client=client,
        tools=tools,
        system_prompt=RESEARCHER_PROMPT,
        description=(
            "Research specialist for finding and synthesizing information. "
            "Has access to web search and file reading capabilities."
        ),
    )
