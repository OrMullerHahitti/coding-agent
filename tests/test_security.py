"""Tests for security utilities."""

import pytest
from pathlib import Path

from coding_agent.tools.security import PathValidator, SecureCommandRunner
from coding_agent.exceptions import PathTraversalError, DisallowedCommandError


class TestPathValidator:
    """Tests for PathValidator class."""

    def test_allows_path_within_root(self, tmp_path):
        """Test that paths within the root are allowed."""
        validator = PathValidator(allowed_roots=[str(tmp_path)])
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validator.validate(str(test_file))
        assert result == test_file

    def test_blocks_path_outside_root(self, tmp_path):
        """Test that paths outside the root are blocked."""
        validator = PathValidator(allowed_roots=[str(tmp_path)])

        with pytest.raises(PathTraversalError):
            validator.validate("/etc/passwd")

    def test_blocks_traversal_attempt(self, tmp_path):
        """Test that path traversal attempts are blocked."""
        validator = PathValidator(allowed_roots=[str(tmp_path)])

        with pytest.raises(PathTraversalError):
            validator.validate(str(tmp_path / ".." / ".." / "etc" / "passwd"))

    def test_is_valid_returns_bool(self, tmp_path):
        """Test that is_valid returns boolean without raising."""
        validator = PathValidator(allowed_roots=[str(tmp_path)])

        assert validator.is_valid(str(tmp_path / "test.txt")) is True
        assert validator.is_valid("/etc/passwd") is False

    def test_add_allowed_root(self, tmp_path):
        """Test adding additional allowed roots."""
        validator = PathValidator(allowed_roots=[str(tmp_path)])
        other_dir = tmp_path.parent / "other"
        other_dir.mkdir(exist_ok=True)

        # Initially blocked
        with pytest.raises(PathTraversalError):
            validator.validate(str(other_dir))

        # After adding, allowed
        validator.add_allowed_root(str(other_dir))
        result = validator.validate(str(other_dir))
        assert result == other_dir.resolve()


class TestSecureCommandRunner:
    """Tests for SecureCommandRunner class."""

    def test_executes_safe_command(self):
        """Test that safe commands execute successfully."""
        runner = SecureCommandRunner()
        stdout, stderr, code = runner.execute("echo hello")
        assert "hello" in stdout
        assert code == 0

    def test_blocks_rm_command(self):
        """Test that rm command is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("rm -rf /")

    def test_blocks_sudo_command(self):
        """Test that sudo command is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("sudo ls")

    def test_blocks_command_chaining_semicolon(self):
        """Test that semicolon command chaining is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("echo hi; rm -rf /")

    def test_blocks_command_chaining_and(self):
        """Test that && command chaining is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("echo hi && rm -rf /")

    def test_blocks_pipe(self):
        """Test that pipe is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("cat /etc/passwd | grep root")

    def test_blocks_redirection(self):
        """Test that output redirection is blocked."""
        runner = SecureCommandRunner()
        with pytest.raises(DisallowedCommandError):
            runner.execute("echo malicious > /etc/passwd")

    def test_allows_delete_when_configured(self):
        """Test that delete is allowed when configured."""
        runner = SecureCommandRunner(allow_delete=True)
        # Should not raise (though it won't actually delete anything)
        assert runner.is_command_allowed("rm test.txt") is True

    def test_allows_network_when_configured(self):
        """Test that network commands are allowed when configured."""
        runner = SecureCommandRunner(allow_network=True)
        assert runner.is_command_allowed("curl http://example.com") is True

    def test_timeout(self):
        """Test that commands timeout."""
        runner = SecureCommandRunner(timeout=1)
        stdout, stderr, code = runner.execute("sleep 10")
        assert "timed out" in stderr
        assert code == -1

    def test_is_command_allowed(self):
        """Test the is_command_allowed helper."""
        runner = SecureCommandRunner()
        assert runner.is_command_allowed("ls -la") is True
        assert runner.is_command_allowed("rm -rf /") is False
        assert runner.is_command_allowed("echo hi; ls") is False
