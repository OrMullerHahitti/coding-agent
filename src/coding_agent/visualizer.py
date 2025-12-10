from typing import List
from .tools.base import BaseTool

class AgentVisualizer:
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools

    def generate_mermaid_graph(self) -> str:
        """
        Generates a Mermaid flowchart representing the agent's structure.
        """
        graph = ["graph TD"]
        graph.append("    User[User] --> Agent[Coding Agent]")
        graph.append("    Agent --> LLM[Together API]")
        graph.append("    LLM --> Agent")
        for tool in self.tools:
            tool_node = f"Tool_{tool.name}[{tool.name}]"
            graph.append(f"    Agent -->|Calls| {tool_node}")
            graph.append(f"    {tool_node} -->|Returns| Agent")
        return "\n".join(graph)
