"""Predefined worker agents for common tasks.

This module provides factory functions to create specialized workers
for coding, research, code review, and codebase exploration tasks.
"""

from .coder import create_coder_worker
from .context import create_context_worker
from .data_analyst import create_data_analyst_worker
from .researcher import create_researcher_worker
from .reviewer import create_reviewer_worker

__all__ = [
    "create_coder_worker",
    "create_context_worker",
    "create_data_analyst_worker",
    "create_researcher_worker",
    "create_reviewer_worker",
]
