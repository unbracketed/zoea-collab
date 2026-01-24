"""
Base class for sandbox executors.

All sandbox types (tmux, docker, vm) implement this interface
for executing commands and managing files.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandboxes.models import SandboxSession

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a command in a sandbox."""

    # Execution status
    success: bool
    exit_code: int = 0

    # Output
    stdout: str = ""
    stderr: str = ""

    # Timing
    duration_seconds: float = 0.0

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def output(self) -> str:
        """Combined stdout and stderr output."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"STDERR:\n{self.stderr}")
        return "\n".join(parts)


@dataclass
class FileInfo:
    """Information about a file in the sandbox."""

    path: str
    exists: bool
    is_file: bool = True
    is_directory: bool = False
    size: int = 0
    content: str | None = None


class BaseSandboxExecutor(ABC):
    """
    Abstract base class for sandbox executors.

    Each sandbox type implements this interface to provide:
    - Command execution
    - File read/write operations
    - Session lifecycle management
    """

    def __init__(self, session: SandboxSession):
        """
        Initialize the executor with a sandbox session.

        Args:
            session: The SandboxSession to execute commands in.
        """
        self.session = session
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def workspace_path(self) -> str:
        """Get the workspace path for this session."""
        return self.session.workspace_path

    @property
    def is_ready(self) -> bool:
        """Check if the sandbox is ready for execution."""
        from sandboxes.models import SessionStatus

        return self.session.status == SessionStatus.READY

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the sandbox environment.

        Creates the necessary resources (container, tmux session, etc.)
        and prepares the workspace.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def terminate(self) -> bool:
        """
        Terminate the sandbox environment.

        Cleans up resources and marks the session as terminated.

        Returns:
            True if termination succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """
        Check if the sandbox is still running.

        Returns:
            True if the sandbox process/container is alive.
        """
        pass

    # =========================================================================
    # Execution Methods
    # =========================================================================

    @abstractmethod
    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """
        Execute a command in the sandbox.

        Args:
            command: The command to execute.
            timeout: Optional timeout in seconds.
            working_directory: Optional directory to execute in.
            environment: Optional additional environment variables.

        Returns:
            ExecutionResult with command output and status.
        """
        pass

    def execute_script(
        self,
        script: str,
        *,
        interpreter: str = "bash",
        timeout: int | None = None,
    ) -> ExecutionResult:
        """
        Execute a script in the sandbox.

        Default implementation writes script to temp file and executes.
        Subclasses can override for more efficient implementations.

        Args:
            script: The script content to execute.
            interpreter: Script interpreter (bash, python, etc.).
            timeout: Optional timeout in seconds.

        Returns:
            ExecutionResult with script output and status.
        """
        import tempfile
        import os

        # Write script to temp file in workspace
        script_name = f"script_{os.urandom(4).hex()}.sh"
        script_path = os.path.join(self.workspace_path, script_name)

        write_result = self.write_file(script_path, script)
        if not write_result:
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stderr="Failed to write script file",
            )

        try:
            # Make executable and run
            self.execute(f"chmod +x {script_path}")
            return self.execute(
                f"{interpreter} {script_path}",
                timeout=timeout,
            )
        finally:
            # Clean up script file
            self.execute(f"rm -f {script_path}")

    # =========================================================================
    # File Operations
    # =========================================================================

    @abstractmethod
    def read_file(self, path: str) -> str | None:
        """
        Read a file from the sandbox.

        Args:
            path: Path to the file (relative to workspace or absolute).

        Returns:
            File content as string, or None if file doesn't exist.
        """
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> bool:
        """
        Write content to a file in the sandbox.

        Args:
            path: Path to the file (relative to workspace or absolute).
            content: Content to write.

        Returns:
            True if write succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in the sandbox.

        Args:
            path: Path to check.

        Returns:
            True if the file exists.
        """
        pass

    def get_file_info(self, path: str) -> FileInfo:
        """
        Get information about a file in the sandbox.

        Args:
            path: Path to the file.

        Returns:
            FileInfo with file details.
        """
        exists = self.file_exists(path)
        if not exists:
            return FileInfo(path=path, exists=False)

        # Check if it's a directory
        result = self.execute(f"test -d {path} && echo 'dir' || echo 'file'")
        is_dir = result.stdout.strip() == "dir"

        # Get size
        size = 0
        if not is_dir:
            size_result = self.execute(f"stat -f%z {path} 2>/dev/null || stat -c%s {path} 2>/dev/null")
            try:
                size = int(size_result.stdout.strip())
            except (ValueError, AttributeError):
                pass

        return FileInfo(
            path=path,
            exists=True,
            is_file=not is_dir,
            is_directory=is_dir,
            size=size,
        )

    def list_files(self, directory: str = ".") -> list[str]:
        """
        List files in a directory.

        Args:
            directory: Directory to list (default: workspace root).

        Returns:
            List of file paths.
        """
        result = self.execute(f"ls -1 {directory}")
        if not result.success:
            return []
        return [f for f in result.stdout.strip().split("\n") if f]

    def delete_file(self, path: str) -> bool:
        """
        Delete a file from the sandbox.

        Args:
            path: Path to the file.

        Returns:
            True if deletion succeeded.
        """
        result = self.execute(f"rm -f {path}")
        return result.success

    def create_directory(self, path: str) -> bool:
        """
        Create a directory in the sandbox.

        Args:
            path: Path to the directory.

        Returns:
            True if creation succeeded.
        """
        result = self.execute(f"mkdir -p {path}")
        return result.success

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def resolve_path(self, path: str) -> str:
        """
        Resolve a path relative to the workspace.

        Args:
            path: Path to resolve.

        Returns:
            Absolute path.
        """
        import os

        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace_path, path)

    def get_environment(self) -> dict[str, str]:
        """
        Get the current environment variables in the sandbox.

        Returns:
            Dict of environment variable names to values.
        """
        result = self.execute("env")
        if not result.success:
            return {}

        env = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
        return env
