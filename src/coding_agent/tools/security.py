"""Security utilities for tool execution.

This module provides security primitives for safe file and command operations:
- PathValidator: Prevents directory traversal attacks
- SecureCommandRunner: Safely executes shell commands with restrictions
"""

import os
import shlex
import subprocess
from pathlib import Path

from ..exceptions import PathTraversalError, DisallowedCommandError


class PathValidator:
    """Validates file paths to prevent directory traversal attacks.

    All file operations should use this validator to ensure paths
    don't escape the allowed directory boundaries.

    Example:
        validator = PathValidator(["/home/user/project"])
        safe_path = validator.validate("./src/main.py")  # OK
        validator.validate("../../etc/passwd")  # Raises PathTraversalError
    """

    def __init__(self, allowed_roots: list[str] | None = None):
        """Initialize with allowed root directories.

        Args:
            allowed_roots: List of allowed root directories.
                          Defaults to current working directory.
        """
        if allowed_roots:
            self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        else:
            self.allowed_roots = [Path.cwd().resolve()]

    def validate(self, path: str) -> Path:
        """Validate and resolve a path.

        Args:
            path: The path to validate (can be relative or absolute)

        Returns:
            Resolved absolute Path object

        Raises:
            PathTraversalError: If path escapes allowed roots
        """
        # Resolve the path to an absolute path
        resolved = Path(path).resolve()

        # Check if it's within any allowed root
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue

        raise PathTraversalError(
            attempted_path=str(resolved),
            allowed_base=str(self.allowed_roots[0])
        )

    def add_allowed_root(self, root: str) -> None:
        """Add an additional allowed root directory.

        Args:
            root: Path to add as allowed root
        """
        self.allowed_roots.append(Path(root).resolve())

    def is_valid(self, path: str) -> bool:
        """Check if a path is valid without raising an exception.

        Args:
            path: The path to check

        Returns:
            True if path is within allowed roots, False otherwise
        """
        try:
            self.validate(path)
            return True
        except PathTraversalError:
            return False


class SecureCommandRunner:
    """Secure command execution with allowlist and sanitization.

    This runner provides safe command execution by:
    - Blocking dangerous commands (rm, sudo, etc.)
    - Preventing shell injection via command chaining
    - Running commands without shell=True
    - Enforcing timeouts

    Example:
        runner = SecureCommandRunner(timeout=30)
        stdout, stderr, code = runner.execute("ls -la")
        # runner.execute("rm -rf /")  # Raises DisallowedCommandError
    """

    # Commands that are always blocked by default
    DEFAULT_BLOCKED_COMMANDS = {
        # Deletion commands
        "rm", "rmdir", "del", "shred",
        # Disk operations
        "mkfs", "dd", "fdisk", "parted", "mount", "umount",
        # Permission/ownership changes
        "chmod", "chown", "chgrp",
        # Privilege escalation
        "sudo", "su", "doas", "pkexec",
        # System control
        "shutdown", "reboot", "init", "systemctl",
        # Network downloads (can be enabled)
        "curl", "wget",
    }

    # Patterns that indicate shell injection attempts
    INJECTION_PATTERNS = [
        ";",    # Command separator
        "&&",   # AND chain
        "||",   # OR chain
        "|",    # Pipe
        "`",    # Command substitution
        "$(",   # Command substitution
        ">",    # Output redirect
        ">>",   # Append redirect
        "<",    # Input redirect
        "\n",   # Newline
        "\r",   # Carriage return
    ]

    def __init__(
        self,
        timeout: int = 60,
        allow_network: bool = False,
        allow_delete: bool = False,
        additional_blocked: set[str] | None = None,
        additional_allowed: set[str] | None = None,
    ):
        """Initialize the secure command runner.

        Args:
            timeout: Maximum execution time in seconds
            allow_network: If True, allows curl/wget
            allow_delete: If True, allows rm/rmdir
            additional_blocked: Extra commands to block
            additional_allowed: Commands to explicitly allow (overrides blocked)
        """
        self.timeout = timeout
        self.blocked = self.DEFAULT_BLOCKED_COMMANDS.copy()

        if additional_blocked:
            self.blocked.update(additional_blocked)

        if allow_network:
            self.blocked.discard("curl")
            self.blocked.discard("wget")

        if allow_delete:
            self.blocked.discard("rm")
            self.blocked.discard("rmdir")

        if additional_allowed:
            self.blocked -= additional_allowed

    def _check_injection(self, command: str) -> None:
        """Check for shell injection patterns.

        Args:
            command: The command string to check

        Raises:
            DisallowedCommandError: If injection pattern found
        """
        for pattern in self.INJECTION_PATTERNS:
            if pattern in command:
                raise DisallowedCommandError(
                    command=command,
                    reason=f"Contains disallowed pattern: '{pattern}'"
                )

    def _parse_command(self, command: str) -> list[str]:
        """Parse command into parts safely.

        Args:
            command: The command string to parse

        Returns:
            List of command parts

        Raises:
            DisallowedCommandError: If command can't be parsed
        """
        try:
            return shlex.split(command)
        except ValueError as e:
            raise DisallowedCommandError(
                command=command,
                reason=f"Failed to parse command: {e}"
            )

    def _check_base_command(self, parts: list[str]) -> None:
        """Check if the base command is allowed.

        Args:
            parts: Parsed command parts

        Raises:
            DisallowedCommandError: If command is blocked
        """
        if not parts:
            raise DisallowedCommandError(
                command="",
                reason="Empty command"
            )

        base_cmd = os.path.basename(parts[0])
        if base_cmd in self.blocked:
            raise DisallowedCommandError(
                command=parts[0],
                reason=f"Command '{base_cmd}' is blocked for security reasons"
            )

    def execute(self, command: str) -> tuple[str, str, int]:
        """Execute a command securely.

        Args:
            command: The command to execute

        Returns:
            Tuple of (stdout, stderr, return_code)

        Raises:
            DisallowedCommandError: If command is blocked or contains injection
        """
        # Check for injection patterns
        self._check_injection(command)

        # Parse the command
        parts = self._parse_command(command)

        # Check if base command is allowed
        self._check_base_command(parts)

        # Execute without shell=True
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                # Explicitly no shell=True for security
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {self.timeout}s", -1
        except FileNotFoundError:
            return "", f"Command not found: {parts[0]}", 127
        except PermissionError:
            return "", f"Permission denied: {parts[0]}", 126

    def is_command_allowed(self, command: str) -> bool:
        """Check if a command would be allowed without executing it.

        Args:
            command: The command to check

        Returns:
            True if command would be allowed, False otherwise
        """
        try:
            self._check_injection(command)
            parts = self._parse_command(command)
            self._check_base_command(parts)
            return True
        except DisallowedCommandError:
            return False
