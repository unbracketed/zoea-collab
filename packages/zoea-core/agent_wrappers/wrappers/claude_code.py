"""
Claude Code wrapper for invoking Claude Code CLI.

Wraps the `claude` CLI tool for executing prompts in a sandbox environment.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, Generator

from .base import AgentOutput, BaseAgentWrapper, ExecutionContext

if TYPE_CHECKING:
    from agent_wrappers.models import ExternalAgentConfig, ExternalAgentRun
    from sandboxes.executors.base import BaseSandboxExecutor

logger = logging.getLogger(__name__)


class ClaudeCodeWrapper(BaseAgentWrapper):
    """
    Wrapper for Claude Code CLI.

    Invokes the `claude` command-line tool to execute prompts,
    optionally in a sandboxed environment.
    """

    # Default CLI command
    DEFAULT_CLI_COMMAND = "claude"

    def __init__(
        self,
        config: ExternalAgentConfig,
        sandbox_executor: BaseSandboxExecutor | None = None,
    ):
        super().__init__(config, sandbox_executor)
        self._cli_command = config.get_cli_command() or self.DEFAULT_CLI_COMMAND

    # =========================================================================
    # Execution Methods
    # =========================================================================

    def execute(
        self,
        prompt: str,
        *,
        context: ExecutionContext | None = None,
        run: ExternalAgentRun | None = None,
    ) -> str:
        """
        Execute a prompt using Claude Code CLI.

        Args:
            prompt: The prompt to execute.
            context: Optional execution context.
            run: Optional ExternalAgentRun to update.

        Returns:
            The agent's response.
        """
        from agent_wrappers.models import AgentRunStatus

        context = context or ExecutionContext(
            working_directory=tempfile.gettempdir()
        )

        # Update run status
        if run:
            run.set_status(AgentRunStatus.RUNNING)

        try:
            # Build the command
            cmd = self._build_command(prompt, context)

            # Execute
            if self.sandbox_executor:
                success, stdout, stderr = self.execute_in_sandbox(
                    cmd,
                    timeout=self.get_timeout(context),
                    working_directory=context.working_directory,
                    environment=context.environment,
                )
            else:
                success, stdout, stderr = self._execute_directly(
                    cmd,
                    context,
                )

            # Combine output
            response = stdout
            if stderr and not success:
                response = f"{stdout}\n\nError:\n{stderr}"

            # Update run with results
            if run:
                run.response = response
                run.output_stream = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                run.set_status(
                    AgentRunStatus.COMPLETED if success else AgentRunStatus.FAILED,
                    "" if success else stderr,
                )

                # Collect artifacts
                if context.capture_artifacts:
                    artifacts = self.collect_artifacts(context)
                    for artifact in artifacts:
                        run.add_artifact(artifact)

            return response

        except subprocess.TimeoutExpired:
            if run:
                run.set_status(AgentRunStatus.TIMEOUT, "Execution timed out")
            raise

        except Exception as e:
            self._logger.exception(f"Error executing Claude Code: {e}")
            if run:
                run.set_status(AgentRunStatus.FAILED, str(e))
            raise

    def execute_streaming(
        self,
        prompt: str,
        *,
        context: ExecutionContext | None = None,
        run: ExternalAgentRun | None = None,
    ) -> Generator[AgentOutput, None, None]:
        """
        Execute a prompt and stream the output.

        Uses subprocess PIPE for real-time output streaming.
        """
        from agent_wrappers.models import AgentRunStatus

        context = context or ExecutionContext(
            working_directory=tempfile.gettempdir()
        )

        if run:
            run.set_status(AgentRunStatus.RUNNING)

        cmd = self._build_command(prompt, context)
        full_output = []

        try:
            # Build full command with shell
            if self.sandbox_executor:
                # Execute through sandbox and stream
                result = self.sandbox_executor.execute(
                    cmd,
                    timeout=self.get_timeout(context),
                    working_directory=context.working_directory,
                    environment=context.environment,
                )

                yield AgentOutput(
                    content=result.stdout,
                    output_type="text",
                    is_final=True,
                )
                full_output.append(result.stdout)

            else:
                # Stream directly using subprocess
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=context.working_directory,
                    env={**os.environ, **context.environment},
                )

                # Stream stdout
                for line in iter(process.stdout.readline, ""):
                    full_output.append(line)
                    yield AgentOutput(
                        content=line,
                        output_type="text",
                        is_final=False,
                    )

                process.wait(timeout=self.get_timeout(context))

                # Yield any stderr
                stderr = process.stderr.read()
                if stderr:
                    yield AgentOutput(
                        content=stderr,
                        output_type="error",
                        is_final=True,
                        metadata={"exit_code": process.returncode},
                    )

            # Update run
            if run:
                run.response = "".join(full_output)
                run.set_status(AgentRunStatus.COMPLETED)

        except Exception as e:
            self._logger.exception(f"Error streaming Claude Code output: {e}")
            if run:
                run.set_status(AgentRunStatus.FAILED, str(e))
            raise

    # =========================================================================
    # Command Building
    # =========================================================================

    def _build_command(
        self,
        prompt: str,
        context: ExecutionContext,
    ) -> str:
        """Build the Claude Code CLI command."""
        parts = [self._cli_command]

        # Add prompt (escaped for shell)
        escaped_prompt = prompt.replace("'", "'\\''")
        parts.append(f"-p '{escaped_prompt}'")

        # Add output format
        output_format = self.get_setting("output_format", "text")
        if output_format == "json":
            parts.append("--output-format json")

        # Add max tokens if configured
        max_tokens = self.get_setting("max_tokens")
        if max_tokens:
            parts.append(f"--max-tokens {max_tokens}")

        # Add model if configured
        model = self.get_setting("model")
        if model:
            parts.append(f"--model {model}")

        # Add any custom CLI args from config
        if self.config.cli_args:
            parts.extend(self.config.cli_args)

        # Add context files (shell-escaped for paths with spaces)
        for file_path in context.context_files:
            parts.append(f"--file {shlex.quote(file_path)}")

        # Add allowed tools/commands if configured (shell-escaped for safety)
        allowed_tools = self.get_setting("allowed_tools")
        if allowed_tools:
            for tool in allowed_tools:
                parts.append(f"--tool {shlex.quote(tool)}")

        return " ".join(parts)

    def _execute_directly(
        self,
        command: str,
        context: ExecutionContext,
    ) -> tuple[bool, str, str]:
        """Execute command directly without sandbox."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=context.working_directory,
                timeout=context.timeout_seconds,
                env={**os.environ, **context.environment},
            )

            return (
                result.returncode == 0,
                result.stdout,
                result.stderr,
            )

        except subprocess.TimeoutExpired as e:
            return False, e.stdout or "", f"Timeout after {context.timeout_seconds}s"

        except Exception as e:
            return False, "", str(e)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate_config(self) -> tuple[bool, str]:
        """Validate Claude Code configuration."""
        is_valid, error = super().validate_config()
        if not is_valid:
            return is_valid, error

        # Check if claude CLI is available
        try:
            result = subprocess.run(
                [self._cli_command, "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False, f"Claude CLI not found or not working: {self._cli_command}"
        except FileNotFoundError:
            return False, f"Claude CLI command not found: {self._cli_command}"
        except Exception as e:
            return False, f"Error checking Claude CLI: {e}"

        return True, ""

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def build_system_prompt(self, context: ExecutionContext | None) -> str:
        """Build system prompt for Claude Code."""
        parts = []

        # Add custom system prompt from config
        custom_system = self.get_setting("system_prompt")
        if custom_system:
            parts.append(custom_system)

        # Add working directory context
        if context:
            parts.append(f"Working directory: {context.working_directory}")

        return "\n\n".join(parts)
