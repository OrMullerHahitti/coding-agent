"""Python REPL tool with security restrictions.

Executes Python code in a sandboxed environment with:
- AST-based validation to block dangerous imports and functions
- Restricted builtins (no exec, eval, open, etc.)
- Persistent namespace for multi-turn interactions
"""

from pprint import pprint
import ast
import sys
import io
from typing import Any

from .base import BaseTool
from ..exceptions import CodeExecutionError


# Modules that are blocked from being imported
BLOCKED_MODULES = {
    # System access
    "os", "subprocess", "shutil", "pathlib",
    # Network
    "socket", "http", "urllib", "requests", "httpx", "aiohttp",
    # Serialization (code injection vectors)
    "pickle", "marshal", "shelve",
    # Low-level access
    "ctypes", "cffi", "mmap",
    # Dynamic imports
    "importlib", "imp",
    # System info
    "platform", "sys",
    # Process management
    "multiprocessing", "threading", "concurrent",
}

# Builtins that are blocked
BLOCKED_BUILTINS = {
    "exec", "eval", "compile",  # Code execution
    "open", "file",  # File access
    "input",  # User input
    "__import__",  # Dynamic imports
    "globals", "locals", "vars",  # Namespace access
    "getattr", "setattr", "delattr",  # Attribute manipulation
    "memoryview", "bytearray",  # Low-level memory
    "breakpoint",  # Debugging
}

# Safe modules that can be imported
ALLOWED_MODULES = {
    "math", "json", "re", "datetime", "time",
    "random", "collections", "itertools", "functools",
    "decimal", "fractions", "statistics",
    "string", "textwrap",
    "copy", "pprint",
    "dataclasses", "typing",
    "operator",
}


class PythonCodeValidator:
    """Validates Python code AST for security issues."""

    def __init__(
        self,
        blocked_modules: set[str] | None = None,
        allowed_modules: set[str] | None = None,
        blocked_builtins: set[str] | None = None,
    ):
        self.blocked_modules = blocked_modules or BLOCKED_MODULES
        self.allowed_modules = allowed_modules or ALLOWED_MODULES
        self.blocked_builtins = blocked_builtins or BLOCKED_BUILTINS

    def validate(self, code: str) -> None:
        """Validate code for security issues.

        Args:
            code: Python code to validate

        Raises:
            CodeExecutionError: If code contains blocked patterns
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise CodeExecutionError(f"Syntax error: {e}")

        for node in ast.walk(tree):
            self._check_node(node)

    def _check_node(self, node: ast.AST) -> None:
        """Check a single AST node for security issues."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._check_import(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                self._check_import(node.module)

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in self.blocked_builtins:
                    raise CodeExecutionError(
                        f"Function '{node.func.id}' is blocked for security"
                    )

    def _check_import(self, module_name: str) -> None:
        """Check if an import is allowed."""
        base_module = module_name.split(".")[0]

        if base_module in self.blocked_modules:
            raise CodeExecutionError(
                f"Import of '{module_name}' is blocked for security"
            )

        if base_module not in self.allowed_modules:
            raise CodeExecutionError(
                f"Import of '{module_name}' is not in the allowed list. "
                f"Allowed: {', '.join(sorted(self.allowed_modules))}"
            )


class PythonREPLTool(BaseTool):
    """Execute Python code in a secure sandbox.

    Security features:
    - Blocked dangerous imports (os, subprocess, etc.)
    - Blocked dangerous builtins (exec, eval, open, etc.)
    - Only allowed safe modules (math, json, etc.)
    - Persistent namespace for multi-turn interactions

    The sandbox is NOT foolproof - it's defense in depth, not a complete
    security boundary. Don't run this tool in production without additional
    isolation (containers, etc.).
    """

    REQUIRES_CONFIRMATION = True
    CONFIRMATION_MESSAGE = "Execute Python code ({len_code} characters)"
    OPERATION_TYPE = "run_code"
    CONFIRMATION_CHECK_ARG = "code"

    def __init__(self):
        """Initialize with a fresh sandboxed namespace."""
        self.validator = PythonCodeValidator()
        self._setup_namespace()

    def _setup_namespace(self) -> None:
        """Set up the restricted execution namespace."""
        import builtins

        # Create restricted builtins
        safe_builtins = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if not name.startswith("_") and name not in BLOCKED_BUILTINS
        }

        # Add safe __import__ that only allows whitelisted modules
        # note: use builtins.__import__ directly, not __builtins__ which can be dict or module
        def safe_import(name, *args, **kwargs):
            base_module = name.split(".")[0]
            if base_module not in ALLOWED_MODULES:
                raise ImportError(f"Import of '{name}' is not allowed")
            return builtins.__import__(name, *args, **kwargs)

        safe_builtins["__import__"] = safe_import

        self.namespace: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "__name__": "__repl__",
        }

    @property
    def name(self) -> str:
        return "python_repl"

    @property
    def description(self) -> str:
        return (
            "Execute Python code in a sandboxed environment. "
            "Some dangerous operations are blocked for security. "
            f"Allowed imports: {', '.join(sorted(ALLOWED_MODULES))}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute.",
                }
            },
            "required": ["code"],
        }

    def execute(self, code: str) -> str:
        """Execute Python code in the sandbox.

        Args:
            code: Python code to execute

        Returns:
            Captured stdout output or error message
        """
        # First, validate the AST
        try:
            self.validator.validate(code)
        except CodeExecutionError as e:
            return f"Security error: {e.reason}"

        # Capture stdout
        old_stdout = sys.stdout
        captured = io.StringIO()
        sys.stdout = captured

        try:
            # Execute in restricted namespace
            exec(code, self.namespace)
            output = captured.getvalue()
            return output if output else "(No output)"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"
        finally:
            sys.stdout = old_stdout

    def reset(self) -> None:
        """Reset the namespace to a fresh state."""
        self._setup_namespace()
