"""
Agent wrappers for different external coding agents.

Provides:
- BaseAgentWrapper: Abstract base class for all wrappers
- ClaudeCodeWrapper: Wrapper for Claude Code CLI
"""

from .base import BaseAgentWrapper, ExecutionContext
from .claude_code import ClaudeCodeWrapper

__all__ = [
    "BaseAgentWrapper",
    "ExecutionContext",
    "ClaudeCodeWrapper",
]
