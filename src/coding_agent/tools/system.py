"""System command execution tool with security restrictions.

Uses SecureCommandRunner to prevent dangerous commands and shell injection.
"""

from typing import Any

from .base import BaseTool
from .security import SecureCommandRunner
from ..exceptions import DisallowedCommandError


# Shared command runner instance with default security settings
_command_runner: SecureCommandRunner | None = None


def get_command_runner() -> SecureCommandRunner:
    """Get or create the shared command runner."""
    global _command_runner
    if _command_runner is None:
        _command_runner = SecureCommandRunner()
    return _command_runner


def configure_command_runner(
    timeout: int = 60,
    allow_network: bool = False,
    allow_delete: bool = False,
    additional_blocked: set[str] | None = None,
    additional_allowed: set[str] | None = None,
) -> None:
    """Configure the command runner security settings.

    Args:
        timeout: Maximum execution time in seconds
        allow_network: Allow curl/wget commands
        allow_delete: Allow rm/rmdir commands
        additional_blocked: Extra commands to block
        additional_allowed: Commands to explicitly allow
    """
    global _command_runner
    _command_runner = SecureCommandRunner(
        timeout=timeout,
        allow_network=allow_network,
        allow_delete=allow_delete,
        additional_blocked=additional_blocked,
        additional_allowed=additional_allowed,
    )


class RunCommandTool(BaseTool):
    """Execute shell commands with security restrictions.

    This tool blocks dangerous commands and prevents shell injection.
    Commands are executed without shell=True for security.

    Blocked by default:
    - Deletion: rm, rmdir, del, shred
    - Disk operations: mkfs, dd, fdisk, etc.
    - Privilege escalation: sudo, su, doas
    - System control: shutdown, reboot
    - Network downloads: curl, wget (can be enabled)

    Shell injection patterns like ;, &&, ||, |, etc. are also blocked.
    """

    REQUIRES_CONFIRMATION = True
    CONFIRMATION_MESSAGE = "Execute command: '{command}'"
    OPERATION_TYPE = "execute"
    CONFIRMATION_CHECK_ARG = "command"

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command. Some dangerous commands are blocked for security. "
            "Commands with shell operators (;, &&, |, etc.) are not supported."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute (without shell operators).",
                }
            },
            "required": ["command"],
        }

    def execute(self, command: str) -> str:
        """Execute a command securely.

        Args:
            command: The command to execute

        Returns:
            Command output (stdout + stderr) or error message
        """
        try:
            runner = get_command_runner()
            stdout, stderr, return_code = runner.execute(command)

            output = stdout
            if stderr:
                output += f"\nError Output:\n{stderr}"
            if return_code != 0:
                output += f"\n(Exit code: {return_code})"

            return output if output.strip() else "(No output)"

        except DisallowedCommandError as e:
            return f"Security error: {e}"
        except Exception as e:
            return f"Error executing command: {e}"
