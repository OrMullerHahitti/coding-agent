"""Filesystem tools with path validation security.

All filesystem operations are validated against allowed root directories
to prevent path traversal attacks.
"""

import os
from typing import Any

from .base import BaseTool
from .security import PathValidator
from ..exceptions import PathTraversalError, ToolExecutionError


# Shared path validator instance - defaults to current working directory
_path_validator: PathValidator | None = None


def get_path_validator() -> PathValidator:
    """Get or create the shared path validator."""
    global _path_validator
    if _path_validator is None:
        _path_validator = PathValidator()
    return _path_validator


def configure_allowed_paths(paths: list[str]) -> None:
    """Configure the allowed paths for filesystem operations.

    Args:
        paths: List of allowed root directories
    """
    global _path_validator
    _path_validator = PathValidator(paths)


class ListDirectoryTool(BaseTool):
    """List contents of a directory with path validation."""

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List the contents of a directory. Returns a list of file and directory names."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the directory to list. Defaults to current directory.",
                }
            },
            "required": [],
        }

    def execute(self, path: str = ".") -> list[str] | str:
        """List directory contents with path validation.

        Args:
            path: Directory path to list

        Returns:
            List of filenames or error message
        """
        try:
            validator = get_path_validator()
            validated_path = validator.validate(path)
            return os.listdir(validated_path)
        except PathTraversalError as e:
            return f"Security error: {e}"
        except FileNotFoundError:
            return f"Error: Directory not found: {path}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error listing directory {path}: {e}"


class ReadFileTool(BaseTool):
    """Read file contents with path validation."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read.",
                }
            },
            "required": ["path"],
        }

    def execute(self, path: str) -> str:
        """Read file contents with path validation.

        Args:
            path: File path to read

        Returns:
            File contents or error message
        """
        try:
            validator = get_path_validator()
            validated_path = validator.validate(path)

            with open(validated_path, "r", encoding="utf-8") as f:
                return f.read()
        except PathTraversalError as e:
            return f"Security error: {e}"
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except UnicodeDecodeError:
            return f"Error: File is not a text file: {path}"
        except Exception as e:
            return f"Error reading file {path}: {e}"


class WriteFileTool(BaseTool):
    """Write content to a file with path validation."""

    REQUIRES_CONFIRMATION = True
    CONFIRMATION_MESSAGE = "Write {len_content} characters to '{path}'"
    OPERATION_TYPE = "write"

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    def execute(self, path: str, content: str) -> str:
        """Write content to file with path validation.

        Args:
            path: File path to write
            content: Content to write

        Returns:
            Success message or error message
        """
        try:
            validator = get_path_validator()
            validated_path = validator.validate(path)

            # Create parent directories if they don't exist
            parent_dir = validated_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)

            with open(validated_path, "w", encoding="utf-8") as f:
                f.write(content)

            return f"Successfully wrote {len(content)} characters to {path}"
        except PathTraversalError as e:
            return f"Security error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error writing to file {path}: {e}"
