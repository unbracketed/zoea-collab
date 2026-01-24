"""
Tmux-based sandbox executor.

Provides lightweight CLI isolation using tmux sessions.
Suitable for development and low-security scenarios.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING

from .base import BaseSandboxExecutor, ExecutionResult

if TYPE_CHECKING:
    from sandboxes.models import SandboxSession

logger = logging.getLogger(__name__)


class TmuxExecutor(BaseSandboxExecutor):
    """
    Executor using tmux sessions for command isolation.

    Creates a dedicated tmux session for each sandbox session,
    allowing commands to run in an isolated terminal environment.
    """

    def __init__(self, session: SandboxSession):
        super().__init__(session)
        self._tmux_session_name = session.tmux_session_name or f"sandbox_{session.session_id.hex[:8]}"

    @property
    def tmux_session_name(self) -> str:
        """Get the tmux session name."""
        return self._tmux_session_name

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    def initialize(self) -> bool:
        """
        Initialize the tmux session and workspace.

        Creates:
        - Workspace directory
        - Tmux session
        """
        from sandboxes.models import SessionStatus

        try:
            # Create workspace directory
            workspace_path = self._create_workspace()
            if not workspace_path:
                self.session.set_status(
                    SessionStatus.ERROR, "Failed to create workspace directory"
                )
                return False

            self.session.workspace_path = workspace_path

            # Create tmux session
            if not self._create_tmux_session():
                self.session.set_status(
                    SessionStatus.ERROR, "Failed to create tmux session"
                )
                return False

            self.session.tmux_session_name = self._tmux_session_name
            self.session.set_status(SessionStatus.READY)

            self._logger.info(
                f"Initialized tmux sandbox: session={self._tmux_session_name}, "
                f"workspace={workspace_path}"
            )
            return True

        except Exception as e:
            self._logger.exception(f"Failed to initialize tmux sandbox: {e}")
            self.session.set_status(SessionStatus.ERROR, str(e))
            return False

    def terminate(self) -> bool:
        """
        Terminate the tmux session and clean up workspace.
        """
        from sandboxes.models import SessionStatus

        try:
            # Kill tmux session
            self._kill_tmux_session()

            # Optionally clean up workspace (configurable)
            # self._cleanup_workspace()

            self.session.set_status(SessionStatus.TERMINATED)
            self._logger.info(f"Terminated tmux sandbox: {self._tmux_session_name}")
            return True

        except Exception as e:
            self._logger.exception(f"Error terminating tmux sandbox: {e}")
            self.session.set_status(SessionStatus.ERROR, str(e))
            return False

    def is_alive(self) -> bool:
        """Check if the tmux session is still running."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self._tmux_session_name],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    # =========================================================================
    # Execution Methods
    # =========================================================================

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
        working_directory: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """
        Execute a command in the tmux session.

        Uses send-keys to send the command and captures output via
        a temporary file.
        """
        if timeout is None:
            timeout = self._get_timeout()

        start_time = time.time()

        try:
            # Build the command with working directory and environment
            full_command = self._build_command(
                command, working_directory, environment
            )

            # Execute using subprocess directly for simplicity
            # (tmux send-keys is async, so we use subprocess for sync execution)
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory or self.workspace_path,
                env=self._get_full_environment(environment),
            )

            duration = time.time() - start_time
            self.session.record_activity()

            return ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stderr=f"Command timed out after {timeout} seconds",
                duration_seconds=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            self._logger.exception(f"Error executing command: {e}")
            return ExecutionResult(
                success=False,
                exit_code=-1,
                stderr=str(e),
                duration_seconds=duration,
            )

    # =========================================================================
    # File Operations
    # =========================================================================

    def read_file(self, path: str) -> str | None:
        """Read a file from the sandbox workspace."""
        resolved_path = self.resolve_path(path)
        try:
            with open(resolved_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as e:
            self._logger.error(f"Error reading file {path}: {e}")
            return None

    def write_file(self, path: str, content: str) -> bool:
        """Write content to a file in the sandbox workspace."""
        resolved_path = self.resolve_path(path)
        try:
            # Ensure parent directory exists
            parent_dir = os.path.dirname(resolved_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(resolved_path, "w") as f:
                f.write(content)
            return True
        except Exception as e:
            self._logger.error(f"Error writing file {path}: {e}")
            return False

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the sandbox workspace."""
        resolved_path = self.resolve_path(path)
        return os.path.exists(resolved_path)

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _create_workspace(self) -> str | None:
        """Create the workspace directory."""
        try:
            # Get base path from config or use system temp
            base_path = None
            if self.session.config:
                base_path = self.session.config.workspace_base_path

            if not base_path:
                base_path = os.path.join(
                    tempfile.gettempdir(), "zoea_sandboxes"
                )

            # Create unique workspace directory
            workspace_name = f"sandbox_{self.session.session_id.hex[:8]}"
            workspace_path = os.path.join(base_path, workspace_name)

            os.makedirs(workspace_path, exist_ok=True)
            return workspace_path

        except Exception as e:
            self._logger.error(f"Failed to create workspace: {e}")
            return None

    def _create_tmux_session(self) -> bool:
        """Create a new tmux session."""
        try:
            result = subprocess.run(
                [
                    "tmux", "new-session",
                    "-d",  # Detached
                    "-s", self._tmux_session_name,
                    "-c", self.session.workspace_path,  # Start in workspace
                ],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            self._logger.error(f"Failed to create tmux session: {e}")
            return False

    def _kill_tmux_session(self) -> bool:
        """Kill the tmux session."""
        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", self._tmux_session_name],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            self._logger.error(f"Failed to kill tmux session: {e}")
            return False

    def _cleanup_workspace(self) -> bool:
        """Remove the workspace directory."""
        try:
            if self.session.workspace_path and os.path.exists(
                self.session.workspace_path
            ):
                shutil.rmtree(self.session.workspace_path)
            return True
        except Exception as e:
            self._logger.error(f"Failed to cleanup workspace: {e}")
            return False

    def _build_command(
        self,
        command: str,
        working_directory: str | None,
        environment: dict[str, str] | None,
    ) -> str:
        """Build the full command with cd and env prefixes."""
        parts = []

        # Add environment exports
        if environment:
            env_exports = " ".join(
                f"{k}={v}" for k, v in environment.items()
            )
            parts.append(env_exports)

        # Add the actual command
        parts.append(command)

        return " ".join(parts)

    def _get_full_environment(
        self, additional_env: dict[str, str] | None
    ) -> dict[str, str]:
        """Get the full environment including config settings."""
        env = os.environ.copy()

        # Add config environment variables
        if self.session.config and self.session.config.environment_variables:
            env.update(self.session.config.environment_variables)

        # Add runtime config environment variables
        if self.session.runtime_config.get("environment_variables"):
            env.update(self.session.runtime_config["environment_variables"])

        # Add additional environment
        if additional_env:
            env.update(additional_env)

        return env

    def _get_timeout(self) -> int:
        """Get the timeout from config or default."""
        if self.session.config:
            return self.session.config.get_timeout_seconds()
        return 600  # 10 minutes default
