"""Logging configuration for the coding agent.

This module provides centralized logging setup with support for both
CLI flags and environment variables.
"""

import logging
import os
import sys


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure logging for the coding agent.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
               If not provided, checks CODING_AGENT_LOG_LEVEL env var.
               Defaults to WARNING if neither is set.

    Returns:
        The configured root logger for the coding_agent package.
    """
    # resolve log level: CLI flag > env var > default
    resolved_level = (
        level
        or os.environ.get("CODING_AGENT_LOG_LEVEL")
        or "WARNING"
    ).upper()

    # validate level
    numeric_level = getattr(logging, resolved_level, None)
    if not isinstance(numeric_level, int):
        print(f"Warning: Invalid log level '{resolved_level}', using WARNING", file=sys.stderr)
        numeric_level = logging.WARNING

    # configure the coding_agent logger
    logger = logging.getLogger("coding_agent")
    logger.setLevel(numeric_level)

    # avoid adding multiple handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(numeric_level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        # update existing handler levels
        for handler in logger.handlers:
            handler.setLevel(numeric_level)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance for the module.
    """
    return logging.getLogger(name)
