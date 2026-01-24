"""
External agent service for unified agent management.

Provides a high-level interface for:
- Running agents with prompts
- Managing agent configurations
- Tracking agent execution runs
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Generator

from django.db import transaction

if TYPE_CHECKING:
    from accounts.models import Account
    from execution.models import ExecutionRun
    from projects.models import Project
    from sandboxes.models import SandboxSession

from .models import (
    AgentRunStatus,
    AgentType,
    ExternalAgentConfig,
    ExternalAgentRun,
)
from .wrappers.base import AgentOutput, BaseAgentWrapper, ExecutionContext

logger = logging.getLogger(__name__)


class ExternalAgentService:
    """
    Service for managing external agent execution.

    Provides a unified interface for running different types of
    external coding agents with consistent tracking and error handling.
    """

    @staticmethod
    def get_wrapper(
        config: ExternalAgentConfig,
        sandbox_session: SandboxSession | None = None,
    ) -> BaseAgentWrapper:
        """
        Get the appropriate wrapper for an agent configuration.

        Args:
            config: The ExternalAgentConfig to get a wrapper for.
            sandbox_session: Optional sandbox session for isolated execution.

        Returns:
            An agent wrapper instance.

        Raises:
            ValueError: If the agent type is not supported.
        """
        from sandboxes.manager import SandboxManager

        # Get sandbox executor if session provided
        executor = None
        if sandbox_session:
            executor = SandboxManager.get_executor(sandbox_session)

        if config.agent_type == AgentType.CLAUDE_CODE:
            from .wrappers.claude_code import ClaudeCodeWrapper

            return ClaudeCodeWrapper(config, executor)

        elif config.agent_type == AgentType.CODEX:
            raise NotImplementedError("Codex wrapper not yet implemented")

        elif config.agent_type == AgentType.OPENCODE:
            raise NotImplementedError("OpenCode wrapper not yet implemented")

        elif config.agent_type == AgentType.SHELLEY:
            raise NotImplementedError("Shelley wrapper not yet implemented")

        elif config.agent_type == AgentType.CUSTOM:
            # Custom agents can use Claude Code wrapper with custom CLI
            from .wrappers.claude_code import ClaudeCodeWrapper

            return ClaudeCodeWrapper(config, executor)

        else:
            raise ValueError(f"Unknown agent type: {config.agent_type}")

    @classmethod
    def run_agent(
        cls,
        prompt: str,
        *,
        config: ExternalAgentConfig | None = None,
        organization: Account,
        project: Project | None = None,
        execution_run: ExecutionRun | None = None,
        sandbox_session: SandboxSession | None = None,
        context: ExecutionContext | None = None,
        user=None,
    ) -> ExternalAgentRun:
        """
        Run an external agent with the given prompt.

        Args:
            prompt: The prompt to execute.
            config: Optional specific config (uses default if not provided).
            organization: The organization context.
            project: Optional project context.
            execution_run: Optional parent ExecutionRun.
            sandbox_session: Optional sandbox for execution.
            context: Optional execution context.
            user: Optional user running the agent.

        Returns:
            ExternalAgentRun with execution results.
        """
        # Get or find config
        if config is None:
            config = cls._get_default_config(organization)

        # Create sandbox if needed and not provided
        if sandbox_session is None and config.default_sandbox:
            from sandboxes.manager import SandboxManager

            sandbox_session, _ = SandboxManager.create_sandbox(
                organization,
                config=config.default_sandbox,
                project=project,
                execution_run=execution_run,
                user=user,
            )

        # Create execution context if not provided
        if context is None:
            context = cls._create_default_context(config, sandbox_session)

        # Create run record
        with transaction.atomic():
            run = ExternalAgentRun.objects.create(
                organization=organization,
                project=project,
                config=config,
                sandbox_session=sandbox_session,
                execution_run=execution_run,
                prompt=prompt,
                status=AgentRunStatus.PENDING,
                runtime_config={
                    "agent_type": config.agent_type,
                    "settings": config.settings,
                    "max_steps": config.max_steps,
                    "timeout_seconds": config.timeout_seconds,
                },
                created_by=user,
            )

        try:
            # Get wrapper and execute
            wrapper = cls.get_wrapper(config, sandbox_session)
            response = wrapper.execute(prompt, context=context, run=run)

            logger.info(
                f"Agent run {run.run_id} completed successfully "
                f"(config={config.name}, org={organization.name})"
            )

            return run

        except Exception as e:
            logger.exception(f"Agent run {run.run_id} failed: {e}")
            run.set_status(AgentRunStatus.FAILED, str(e))
            return run

    @classmethod
    def run_agent_streaming(
        cls,
        prompt: str,
        *,
        config: ExternalAgentConfig | None = None,
        organization: Account,
        project: Project | None = None,
        execution_run: ExecutionRun | None = None,
        sandbox_session: SandboxSession | None = None,
        context: ExecutionContext | None = None,
        user=None,
    ) -> Generator[tuple[ExternalAgentRun, AgentOutput], None, None]:
        """
        Run an external agent with streaming output.

        Args:
            prompt: The prompt to execute.
            config: Optional specific config.
            organization: The organization context.
            project: Optional project context.
            execution_run: Optional parent ExecutionRun.
            sandbox_session: Optional sandbox for execution.
            context: Optional execution context.
            user: Optional user running the agent.

        Yields:
            Tuples of (ExternalAgentRun, AgentOutput).
        """
        if config is None:
            config = cls._get_default_config(organization)

        if sandbox_session is None and config.default_sandbox:
            from sandboxes.manager import SandboxManager

            sandbox_session, _ = SandboxManager.create_sandbox(
                organization,
                config=config.default_sandbox,
                project=project,
                execution_run=execution_run,
                user=user,
            )

        if context is None:
            context = cls._create_default_context(config, sandbox_session)

        with transaction.atomic():
            run = ExternalAgentRun.objects.create(
                organization=organization,
                project=project,
                config=config,
                sandbox_session=sandbox_session,
                execution_run=execution_run,
                prompt=prompt,
                status=AgentRunStatus.PENDING,
                runtime_config={
                    "agent_type": config.agent_type,
                    "settings": config.settings,
                },
                created_by=user,
            )

        try:
            wrapper = cls.get_wrapper(config, sandbox_session)

            for output in wrapper.execute_streaming(prompt, context=context, run=run):
                yield run, output

        except Exception as e:
            logger.exception(f"Agent run {run.run_id} failed during streaming: {e}")
            run.set_status(AgentRunStatus.FAILED, str(e))
            raise

    @classmethod
    def get_config(
        cls,
        organization: Account,
        *,
        agent_type: str | None = None,
        config_id: int | None = None,
    ) -> ExternalAgentConfig | None:
        """
        Get an agent configuration.

        Args:
            organization: The organization context.
            agent_type: Optional filter by agent type.
            config_id: Optional specific config ID.

        Returns:
            ExternalAgentConfig or None if not found.
        """
        queryset = ExternalAgentConfig.objects.filter(
            organization=organization,
            is_enabled=True,
        )

        if config_id:
            return queryset.filter(id=config_id).first()

        if agent_type:
            queryset = queryset.filter(agent_type=agent_type)

        # Try to get default first
        config = queryset.filter(is_default=True).first()
        if config:
            return config

        # Fall back to any config
        return queryset.first()

    @classmethod
    def list_configs(
        cls,
        organization: Account,
        *,
        agent_type: str | None = None,
        include_disabled: bool = False,
    ) -> list[ExternalAgentConfig]:
        """
        List agent configurations.

        Args:
            organization: The organization context.
            agent_type: Optional filter by agent type.
            include_disabled: Whether to include disabled configs.

        Returns:
            List of ExternalAgentConfig objects.
        """
        queryset = ExternalAgentConfig.objects.filter(organization=organization)

        if not include_disabled:
            queryset = queryset.filter(is_enabled=True)

        if agent_type:
            queryset = queryset.filter(agent_type=agent_type)

        return list(queryset.order_by("-is_default", "-created_at"))

    @classmethod
    def _get_default_config(cls, organization: Account) -> ExternalAgentConfig:
        """Get or create a default agent config."""
        config = cls.get_config(organization)

        if config:
            return config

        # Create default Claude Code config
        config = ExternalAgentConfig.objects.create(
            organization=organization,
            name="Default Claude Code",
            description="Auto-created default Claude Code configuration",
            agent_type=AgentType.CLAUDE_CODE,
            is_default=True,
            settings={
                "output_format": "text",
            },
        )

        logger.info(
            f"Created default agent config for organization {organization.name}"
        )
        return config

    @classmethod
    def _create_default_context(
        cls,
        config: ExternalAgentConfig,
        sandbox_session: SandboxSession | None,
    ) -> ExecutionContext:
        """Create a default execution context."""
        import tempfile

        working_dir = tempfile.gettempdir()

        if sandbox_session and sandbox_session.workspace_path:
            working_dir = sandbox_session.workspace_path

        return ExecutionContext(
            working_directory=working_dir,
            max_steps=config.max_steps,
            timeout_seconds=config.timeout_seconds,
        )


def run_external_agent(
    prompt: str,
    organization: Account,
    **kwargs,
) -> ExternalAgentRun:
    """
    Convenience function to run an external agent.

    Args:
        prompt: The prompt to execute.
        organization: The organization context.
        **kwargs: Additional arguments for ExternalAgentService.run_agent.

    Returns:
        ExternalAgentRun with execution results.
    """
    return ExternalAgentService.run_agent(
        prompt,
        organization=organization,
        **kwargs,
    )
