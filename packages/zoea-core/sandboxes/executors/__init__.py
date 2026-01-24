"""
Sandbox executors for different execution environments.

Provides:
- BaseSandboxExecutor: Abstract base class for all executors
- TmuxExecutor: Lightweight CLI isolation via tmux
- DockerExecutor: Full environment isolation via Docker
"""

from .base import BaseSandboxExecutor, ExecutionResult
from .tmux import TmuxExecutor

__all__ = [
    "BaseSandboxExecutor",
    "ExecutionResult",
    "TmuxExecutor",
]
