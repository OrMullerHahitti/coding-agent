"""Prompt construction and formatting utilities.

This module handles the creation and formatting of prompts and messages
for the coding agent.
"""

from ..clients.base import BaseLLMClient
from ..tools.base import BaseTool
from ..types import MessageRole, UnifiedMessage


class PromptBuilder:
    """Constructs and formats prompts for the agent.

    This class handles the formatting of system prompts with tool descriptions
    and the creation of unified messages for different roles.
    """

    def __init__(self, base_prompt: str):
        """Initialize the prompt builder.

        Args:
            base_prompt: The base system prompt template.
        """
        self.base_prompt = base_prompt

    def format_system_prompt(self, tools: list[BaseTool], client: BaseLLMClient) -> str:
        """Format the system prompt with tool descriptions.

        Args:
            tools: List of available tools.
            client: The LLM client (used for provider-specific formatting).

        Returns:
            Formatted system prompt string.
        """
        return client.format_system_prompt(self.base_prompt, tools)

    def build_system_message(self, content: str) -> UnifiedMessage:
        """Create a system message.

        Args:
            content: The system message content.

        Returns:
            A UnifiedMessage with SYSTEM role.
        """
        return UnifiedMessage(role=MessageRole.SYSTEM, content=content)

    def build_user_message(self, content: str) -> UnifiedMessage:
        """Create a user message.

        Args:
            content: The user's message content.

        Returns:
            A UnifiedMessage with USER role.
        """
        return UnifiedMessage(role=MessageRole.USER, content=content)

    def build_tool_result(
        self,
        tool_call_id: str,
        name: str,
        content: str,
    ) -> UnifiedMessage:
        """Create a tool result message.

        Args:
            tool_call_id: The ID of the tool call this result is for.
            name: The name of the tool.
            content: The result content.

        Returns:
            A UnifiedMessage with TOOL role.
        """
        return UnifiedMessage(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )
