"""Data analyst worker agent factory.

Creates a worker specialized for dataset loading, exploration, transformation, and export.
"""

from ...clients.base import BaseLLMClient
from ...tools.ask_user import AskUserTool
from ...tools.data_analysis import (
    ClearDatasetsTool,
    DatasetDescribeTool,
    DatasetFilterTool,
    DatasetGroupByAggTool,
    DatasetHeadTool,
    DatasetInfoTool,
    DatasetSampleTool,
    DatasetSelectColumnsTool,
    DatasetSortTool,
    DatasetTailTool,
    DatasetValueCountsTool,
    ExportDatasetTool,
    ListDatasetsTool,
    LoadDatasetTool,
    RemoveDatasetTool,
    SaveBarPlotTool,
    SaveHistogramPlotTool,
    SaveScatterPlotTool,
)
from ...tools.filesystem import ListDirectoryTool, ReadFileTool, WriteFileTool
from ...tools.python_repl import PythonREPLTool
from ...tools.system import RunCommandTool
from ..prompts import DATA_ANALYST_PROMPT
from ..worker import WorkerAgent


def create_data_analyst_worker(
    client: BaseLLMClient,
    include_dangerous_tools: bool = True,
) -> WorkerAgent:
    """Create a data analyst worker agent.

    Args:
        client: LLM client for the worker.
        include_dangerous_tools: Whether to include tools that write files or run commands/code.

    Returns:
        Configured data_analyst WorkerAgent.
    """
    tools = [
        AskUserTool(use_interrupt=True),
        ReadFileTool(),
        ListDirectoryTool(),
        LoadDatasetTool(),
        ListDatasetsTool(),
        RemoveDatasetTool(),
        ClearDatasetsTool(),
        DatasetInfoTool(),
        DatasetHeadTool(),
        DatasetTailTool(),
        DatasetSampleTool(),
        DatasetDescribeTool(),
        DatasetValueCountsTool(),
        DatasetSelectColumnsTool(),
        DatasetFilterTool(),
        DatasetSortTool(),
        DatasetGroupByAggTool(),
    ]

    if include_dangerous_tools:
        tools.extend([
            WriteFileTool(),
            RunCommandTool(),
            PythonREPLTool(),
            ExportDatasetTool(),
            SaveBarPlotTool(),
            SaveHistogramPlotTool(),
            SaveScatterPlotTool(),
        ])

    return WorkerAgent(
        name="data_analyst",
        client=client,
        tools=tools,
        system_prompt=DATA_ANALYST_PROMPT,
        description=(
            "Data analysis specialist for loading, exploring, transforming, and exporting datasets. "
            "Has access to dedicated data-analysis tools and can optionally write files and save plots."
        ),
    )
