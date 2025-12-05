"""Tests for tool implementations."""

import os
import pytest

from coding_agent.tools.calculator import CalculatorTool
from coding_agent.tools.filesystem import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
    configure_allowed_paths,
)
from coding_agent.tools.system import RunCommandTool, configure_command_runner
from coding_agent.tools.python_repl import PythonREPLTool


class TestCalculatorTool:
    """Tests for CalculatorTool."""

    def test_add(self):
        tool = CalculatorTool()
        assert tool.execute("add", 5, 3) == 8

    def test_subtract(self):
        tool = CalculatorTool()
        assert tool.execute("subtract", 10, 3) == 7

    def test_multiply(self):
        tool = CalculatorTool()
        assert tool.execute("multiply", 4, 5) == 20

    def test_divide(self):
        tool = CalculatorTool()
        assert tool.execute("divide", 20, 4) == 5

    def test_divide_by_zero(self):
        tool = CalculatorTool()
        result = tool.execute("divide", 10, 0)
        assert "Error" in result

    def test_invalid_operation(self):
        tool = CalculatorTool()
        result = tool.execute("power", 2, 3)
        assert "Unknown" in result or "Error" in result


class TestFilesystemTools:
    """Tests for filesystem tools with security."""

    def test_write_and_read(self, tmp_path):
        """Test writing and reading a file within allowed path."""
        # Configure allowed paths to include temp directory
        configure_allowed_paths([str(tmp_path)])

        write_tool = WriteFileTool()
        read_tool = ReadFileTool()

        test_file = tmp_path / "test.txt"

        # Write
        result = write_tool.execute(str(test_file), "Hello World")
        assert "Successfully wrote" in result
        assert test_file.read_text() == "Hello World"

        # Read
        content = read_tool.execute(str(test_file))
        assert content == "Hello World"

    def test_list_directory(self, tmp_path):
        """Test listing directory contents."""
        configure_allowed_paths([str(tmp_path)])

        # Create some files
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()

        list_tool = ListDirectoryTool()
        files = list_tool.execute(str(tmp_path))

        assert "file1.txt" in files
        assert "file2.txt" in files

    def test_path_traversal_blocked(self, tmp_path):
        """Test that path traversal is blocked."""
        configure_allowed_paths([str(tmp_path)])

        read_tool = ReadFileTool()
        result = read_tool.execute("/etc/passwd")

        assert "Security error" in result

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading a file that doesn't exist."""
        configure_allowed_paths([str(tmp_path)])

        read_tool = ReadFileTool()
        result = read_tool.execute(str(tmp_path / "nonexistent.txt"))

        assert "Error" in result
        assert "not found" in result.lower()


class TestRunCommandTool:
    """Tests for RunCommandTool with security."""

    def test_safe_command(self):
        """Test executing a safe command."""
        tool = RunCommandTool()
        output = tool.execute("echo hello")
        assert "hello" in output

    def test_blocked_command(self):
        """Test that dangerous commands are blocked."""
        tool = RunCommandTool()
        output = tool.execute("rm -rf /")
        assert "Security error" in output

    def test_blocked_shell_injection(self):
        """Test that shell injection is blocked."""
        tool = RunCommandTool()
        output = tool.execute("echo hi; rm -rf /")
        assert "Security error" in output


class TestPythonREPLTool:
    """Tests for PythonREPLTool with security."""

    def test_simple_print(self):
        """Test simple print execution."""
        tool = PythonREPLTool()
        output = tool.execute("print(5 + 5)")
        assert "10" in output.strip()

    def test_persistence(self):
        """Test that namespace persists between calls."""
        tool = PythonREPLTool()
        tool.execute("x = 10")
        output = tool.execute("print(x)")
        assert "10" in output.strip()

    def test_safe_import(self):
        """Test importing allowed modules."""
        tool = PythonREPLTool()
        output = tool.execute("import math\nprint(math.pi)")
        assert "3.14" in output

    def test_blocked_import(self):
        """Test that dangerous imports are blocked."""
        tool = PythonREPLTool()
        output = tool.execute("import os")
        assert "Security error" in output or "not allowed" in output.lower()

    def test_blocked_subprocess(self):
        """Test that subprocess import is blocked."""
        tool = PythonREPLTool()
        output = tool.execute("import subprocess")
        assert "Security error" in output or "not allowed" in output.lower()

    def test_blocked_exec(self):
        """Test that exec is blocked."""
        tool = PythonREPLTool()
        output = tool.execute("exec('print(1)')")
        assert "Security error" in output or "blocked" in output.lower()

    def test_reset(self):
        """Test resetting the namespace."""
        tool = PythonREPLTool()
        tool.execute("x = 10")
        tool.reset()
        output = tool.execute("print(x)")
        assert "Error" in output  # x should not exist after reset
