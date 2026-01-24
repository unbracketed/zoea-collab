"""
Base class for external agent wrappers.

All agent types (Claude Code, Codex, OpenCode, etc.) implement this
interface for executing prompts and managing agent interactions.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from agent_wrappers.models import ExternalAgentConfig, ExternalAgentRun
    from sandboxes.executors.base import BaseSandboxExecutor

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for agent execution."""

    # Working directory for the agent
    working_directory: str

    # Files to include as context
    context_files: list[str] = field(default_factory=list)

    # Environment variables
    environment: dict[str, str] = field(default_factory=dict)

    # Additional configuration
    max_steps: int = 50
    timeout_seconds: int = 600

    # Execution mode
    stream_output: bool = False
    capture_artifacts: bool = True


@dataclass
class AgentOutput:
    """Output from an agent execution step."""

    # Output content
    content: str

    # Output type (text, code, tool_call, etc.)
    output_type: str = "text"

    # Whether this is a final response
    is_final: bool = False

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgentWrapper(ABC):
    """
    Abstract base class for external agent wrappers.

    Each agent type implements this interface to provide:
    - Prompt execution
    - Output streaming
    - Artifact collection
    """

    def __init__(
        self,
        config: ExternalAgentConfig,
        sandbox_executor: BaseSandboxExecutor | None = None,
    ):
        """
        Initialize the wrapper with configuration.

        Args:
            config: The ExternalAgentConfig for this agent.
            sandbox_executor: Optional sandbox executor for isolated execution.
        """
        self.config = config
        self.sandbox_executor = sandbox_executor
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def agent_type(self) -> str:
        """Get the agent type."""
        return self.config.agent_type

    # =========================================================================
    # Execution Methods
    # =========================================================================

    @abstractmethod
    def execute(
        self,
        prompt: str,
        *,
        context: ExecutionContext | None = None,
        run: ExternalAgentRun | None = None,
    ) -> str:
        """
        Execute a prompt and return the response.

        Args:
            prompt: The prompt to execute.
            context: Optional execution context.
            run: Optional ExternalAgentRun to update.

        Returns:
            The agent's response as a string.
        """
        pass

    def execute_streaming(
        self,
        prompt: str,
        *,
        context: ExecutionContext | None = None,
        run: ExternalAgentRun | None = None,
    ) -> Generator[AgentOutput, None, None]:
        """
        Execute a prompt and stream the output.

        Default implementation calls execute() and yields single result.
        Subclasses can override for true streaming support.

        Args:
            prompt: The prompt to execute.
            context: Optional execution context.
            run: Optional ExternalAgentRun to update.

        Yields:
            AgentOutput objects as they're produced.
        """
        response = self.execute(prompt, context=context, run=run)
        yield AgentOutput(content=response, is_final=True)

    # =========================================================================
    # Configuration Methods
    # =========================================================================

    def get_credential(self, key: str, default: Any = None) -> Any:
        """Get a credential from the config."""
        return self.config.get_credential(key, default)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting from the config."""
        return self.config.get_setting(key, default)

    def get_timeout(self, context: ExecutionContext | None) -> int:
        """Get the timeout in seconds."""
        if context and context.timeout_seconds:
            return context.timeout_seconds
        return self.config.timeout_seconds

    def get_max_steps(self, context: ExecutionContext | None) -> int:
        """Get the maximum number of steps."""
        if context and context.max_steps:
            return context.max_steps
        return self.config.max_steps

    # =========================================================================
    # Sandbox Execution Helpers
    # =========================================================================

    def execute_in_sandbox(
        self,
        command: str,
        *,
        timeout: int | None = None,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> tuple[bool, str, str]:
        """
        Execute a command in the sandbox.

        Args:
            command: The command to execute.
            timeout: Optional timeout in seconds.
            working_directory: Optional working directory.
            environment: Optional environment variables.

        Returns:
            Tuple of (success, stdout, stderr).
        """
        if not self.sandbox_executor:
            raise RuntimeError("No sandbox executor configured")

        result = self.sandbox_executor.execute(
            command,
            timeout=timeout,
            working_directory=working_directory,
            environment=environment,
        )

        return result.success, result.stdout, result.stderr

    def read_file_in_sandbox(self, path: str) -> str | None:
        """Read a file from the sandbox."""
        if not self.sandbox_executor:
            raise RuntimeError("No sandbox executor configured")
        return self.sandbox_executor.read_file(path)

    def write_file_in_sandbox(self, path: str, content: str) -> bool:
        """Write a file in the sandbox."""
        if not self.sandbox_executor:
            raise RuntimeError("No sandbox executor configured")
        return self.sandbox_executor.write_file(path, content)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def build_system_prompt(self, context: ExecutionContext | None) -> str:
        """
        Build the system prompt for the agent.

        Default implementation returns empty string.
        Subclasses can override for agent-specific system prompts.
        """
        return ""

    def collect_artifacts(
        self,
        context: ExecutionContext,
        before_files: dict[str, str] | None = None,
    ) -> list[dict]:
        """
        Collect artifacts (created/modified files) after execution.

        Args:
            context: The execution context.
            before_files: Optional dict of file paths to content before execution.

        Returns:
            List of artifact dicts with path, action (created/modified), etc.
        """
        if not self.sandbox_executor:
            return []

        artifacts = []

        # List files in working directory
        try:
            files = self.sandbox_executor.list_files(context.working_directory)

            for file_path in files:
                full_path = f"{context.working_directory}/{file_path}"

                if before_files is None:
                    # If no before state, treat all as potential artifacts
                    artifacts.append({
                        "path": file_path,
                        "action": "exists",
                    })
                elif file_path not in before_files:
                    # New file
                    artifacts.append({
                        "path": file_path,
                        "action": "created",
                    })
                else:
                    # Check if modified
                    current_content = self.sandbox_executor.read_file(full_path)
                    if current_content != before_files.get(file_path):
                        artifacts.append({
                            "path": file_path,
                            "action": "modified",
                        })

        except Exception as e:
            self._logger.error(f"Error collecting artifacts: {e}")

        return artifacts

    def validate_config(self) -> tuple[bool, str]:
        """
        Validate that the configuration is correct.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not self.config.is_enabled:
            return False, "Agent configuration is disabled"

        # Subclasses can add additional validation
        return True, ""
