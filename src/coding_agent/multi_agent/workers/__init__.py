"""Predefined worker agents for common tasks.

This module provides factory functions to create specialized workers
for coding, research, and code review tasks.
"""

from .coder import create_coder_worker
from .researcher import create_researcher_worker
from .reviewer import create_reviewer_worker

__all__ = [
    "create_coder_worker",
    "create_researcher_worker",
    "create_reviewer_worker",
]
