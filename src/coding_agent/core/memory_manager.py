"""Memory and state management for the agent.

This module handles conversation history and pending state
for interrupts and confirmations.
"""

from ..types import (
    ConfirmationInfo,
    InterruptInfo,
    MessageRole,
    ToolCall,
    UnifiedMessage,
)


class MemoryManager:
    """Manages conversation history and pending state.

    This class encapsulates all history operations and state management
    for the agent, including:
    - Conversation history (list of UnifiedMessages)
    - Pending interrupt state
    - Pending confirmation state
    - Pending tool calls
    """

    def __init__(self):
        """Initialize the memory manager with empty state."""
        self.history: list[UnifiedMessage] = []
        self._pending_interrupt: InterruptInfo | None = None
        self._pending_confirmation: ConfirmationInfo | None = None
        self._pending_tool_calls: list[ToolCall] | None = None

    def add_message(self, message: UnifiedMessage) -> None:
        """Add a message to conversation history.

        Args:
            message: The message to add.
        """
        self.history.append(message)

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Add a tool result message to conversation history.

        Args:
            tool_call_id: The ID of the tool call.
            name: The name of the tool.
            content: The result content.
        """
        self.history.append(UnifiedMessage(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        ))

    def clear(self, keep_system: bool = True) -> None:
        """Clear conversation history.

        Args:
            keep_system: If True, preserve the system message.
        """
        if keep_system and self.history:
            system_msg = self.history[0]
            self.history = []
            if system_msg.role == MessageRole.SYSTEM:
                self.history.append(system_msg)
        else:
            self.history = []

        # clear all pending state
        self._pending_interrupt = None
        self._pending_confirmation = None
        self._pending_tool_calls = None

    def get_history(self) -> list[dict]:
        """Export history as list of dicts.

        Returns:
            List of message dictionaries.
        """
        return [msg.to_dict() for msg in self.history]

    # interrupt state management

    @property
    def pending_interrupt(self) -> InterruptInfo | None:
        """Get the pending interrupt info."""
        return self._pending_interrupt

    def set_pending_interrupt(
        self,
        info: InterruptInfo,
        remaining_calls: list[ToolCall] | None = None,
    ) -> None:
        """Store interrupt state for resumption.

        Args:
            info: The interrupt information.
            remaining_calls: Remaining tool calls to execute after resumption.
        """
        self._pending_interrupt = info
        self._pending_tool_calls = remaining_calls

    def clear_interrupt(self) -> tuple[InterruptInfo | None, list[ToolCall] | None]:
        """Clear and return the pending interrupt state.

        Returns:
            Tuple of (interrupt_info, remaining_tool_calls).
        """
        info = self._pending_interrupt
        remaining = self._pending_tool_calls
        self._pending_interrupt = None
        self._pending_tool_calls = None
        return info, remaining

    # confirmation state management

    @property
    def pending_confirmation(self) -> ConfirmationInfo | None:
        """Get the pending confirmation info."""
        return self._pending_confirmation

    def set_pending_confirmation(
        self,
        info: ConfirmationInfo,
        remaining_calls: list[ToolCall] | None = None,
    ) -> None:
        """Store confirmation state for resumption.

        Args:
            info: The confirmation information.
            remaining_calls: Remaining tool calls to execute after resumption.
        """
        self._pending_confirmation = info
        self._pending_tool_calls = remaining_calls

    def clear_confirmation(self) -> tuple[ConfirmationInfo | None, list[ToolCall] | None]:
        """Clear and return the pending confirmation state.

        Returns:
            Tuple of (confirmation_info, remaining_tool_calls).
        """
        info = self._pending_confirmation
        remaining = self._pending_tool_calls
        self._pending_confirmation = None
        self._pending_tool_calls = None
        return info, remaining

    @property
    def pending_tool_calls(self) -> list[ToolCall] | None:
        """Get the pending tool calls."""
        return self._pending_tool_calls

    def cleanup_pending_state(self) -> None:
        """Clean up any pending confirmation/interrupt state.

        If there's a pending confirmation or interrupt, adds a cancellation
        message to history so the LLM knows the operation was abandoned.
        """
        if self._pending_confirmation:
            self.add_tool_result(
                self._pending_confirmation.tool_call_id,
                self._pending_confirmation.tool_name,
                "Operation abandoned: user sent a new message before confirming.",
            )
            self._pending_confirmation = None

        if self._pending_interrupt:
            self.add_tool_result(
                self._pending_interrupt.tool_call_id,
                self._pending_interrupt.tool_name,
                "Question abandoned: user sent a new message before responding.",
            )
            self._pending_interrupt = None

        self._pending_tool_calls = None

    def has_pending_state(self) -> bool:
        """Check if there's any pending state.

        Returns:
            True if there's a pending interrupt or confirmation.
        """
        return self._pending_interrupt is not None or self._pending_confirmation is not None
