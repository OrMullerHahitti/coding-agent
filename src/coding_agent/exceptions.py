"""Custom exception hierarchy for the coding agent.

This module defines all custom exceptions used throughout the agent,
organized into logical categories: client errors, tool errors, and security errors.
"""


class AgentError(Exception):
    """Base exception for all agent errors."""


# =============================================================================
# Control Flow - Not errors, but control flow mechanisms
# =============================================================================

class InterruptRequested(AgentError):
    """Raised when a tool requests an interrupt for user input.

    This is a control flow mechanism, not an error. It signals that the
    agent should pause execution and wait for user input before continuing.

    Used by tools like AskUserTool to implement human-in-the-loop patterns
    without blocking the execution thread.

    Attributes:
        tool_name: Name of the tool requesting the interrupt
        tool_call_id: ID of the tool call for resumption
        question: The question to ask the user
        context: Optional additional context
    """

    def __init__(
        self,
        tool_name: str,
        tool_call_id: str,
        question: str,
        context: dict | None = None,
    ):
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id
        self.question = question
        self.context = context
        super().__init__(f"Interrupt requested by {tool_name}: {question}")


class ConfirmationRequested(AgentError):
    """Raised when a tool requires user confirmation before execution.

    This is a control flow mechanism for dangerous operations. It signals that
    the agent should pause and ask for user permission before proceeding.

    Used by tools that modify files, execute commands, or run code.

    Attributes:
        tool_name: Name of the tool requesting confirmation
        tool_call_id: ID of the tool call for resumption
        message: Description of what will happen if confirmed
        operation: Type of operation (write, execute, run_code)
        arguments: The arguments that will be passed to the tool
    """

    def __init__(
        self,
        tool_name: str,
        tool_call_id: str,
        message: str,
        operation: str,
        arguments: dict,
    ):
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id
        self.message = message
        self.operation = operation
        self.arguments = arguments
        super().__init__(f"Confirmation required for {tool_name}: {message}")


# =============================================================================
# Client Errors - Issues with LLM API interactions
# =============================================================================

class ClientError(AgentError):
    """Base class for LLM client errors."""


class AuthenticationError(ClientError):
    """API key is invalid or missing."""


class RateLimitError(ClientError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float | None = None):
        self.retry_after = retry_after
        if retry_after:
            message = f"{message}. Retry after: {retry_after}s"
        super().__init__(message)


class ContextLengthError(ClientError):
    """Context length exceeded for model."""

    def __init__(self, max_tokens: int, requested_tokens: int | None = None):
        self.max_tokens = max_tokens
        self.requested_tokens = requested_tokens
        if requested_tokens:
            message = f"Context length exceeded: {requested_tokens} > {max_tokens} tokens"
        else:
            message = f"Context length exceeded model limit of {max_tokens} tokens"
        super().__init__(message)


class ModelNotFoundError(ClientError):
    """Requested model does not exist."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model not found: {model_name}")


class ProviderUnavailableError(ClientError):
    """Provider API is temporarily unavailable."""



class InvalidResponseError(ClientError):
    """Response from provider could not be parsed."""



# =============================================================================
# Tool Errors - Issues with tool execution
# =============================================================================

class ToolError(AgentError):
    """Base class for tool execution errors."""



class ToolNotFoundError(ToolError):
    """Requested tool does not exist."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


class ToolExecutionError(ToolError):
    """Tool execution failed."""

    def __init__(self, tool_name: str, cause: Exception | str):
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"Tool '{tool_name}' execution failed: {cause}")


class ToolValidationError(ToolError):
    """Tool arguments failed validation."""

    def __init__(self, tool_name: str, errors: list[str]):
        self.tool_name = tool_name
        self.errors = errors
        super().__init__(f"Tool '{tool_name}' validation failed: {', '.join(errors)}")


class ToolTimeoutError(ToolError):
    """Tool execution timed out."""

    def __init__(self, tool_name: str, timeout: float):
        self.tool_name = tool_name
        self.timeout = timeout
        super().__init__(f"Tool '{tool_name}' timed out after {timeout}s")


# =============================================================================
# Security Errors - Security-related issues
# =============================================================================

class SecurityError(AgentError):
    """Base class for security-related errors."""
    pass


class PathTraversalError(SecurityError):
    """Attempted path traversal attack."""

    def __init__(self, attempted_path: str, allowed_base: str):
        self.attempted_path = attempted_path
        self.allowed_base = allowed_base
        super().__init__(
            f"Path traversal blocked: '{attempted_path}' is outside allowed directory '{allowed_base}'"
        )


class DisallowedCommandError(SecurityError):
    """Attempted to run a disallowed command."""

    def __init__(self, command: str, reason: str):
        self.command = command
        self.reason = reason
        super().__init__(f"Command disallowed: '{command}'. Reason: {reason}")


class CodeExecutionError(SecurityError):
    """Dangerous code execution blocked."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Code execution blocked: {reason}")
