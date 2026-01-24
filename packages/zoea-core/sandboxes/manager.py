"""
Sandbox manager for creating and managing execution environments.

Provides a high-level interface for:
- Creating sandboxes from configurations
- Getting executors for sandbox sessions
- Managing sandbox lifecycle
"""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

from django.db import transaction

if TYPE_CHECKING:
    from accounts.models import Account
    from execution.models import ExecutionRun
    from projects.models import Project

from .executors.base import BaseSandboxExecutor
from .models import SandboxConfig, SandboxSession, SandboxType, SessionStatus

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Manager for sandbox lifecycle operations.

    Handles creation, retrieval, and termination of sandbox sessions
    with support for different executor types.
    """

    @staticmethod
    def get_executor(session: SandboxSession) -> BaseSandboxExecutor:
        """
        Get the appropriate executor for a sandbox session.

        Args:
            session: The SandboxSession to get an executor for.

        Returns:
            An executor instance for the session's sandbox type.

        Raises:
            ValueError: If the sandbox type is not supported.
        """
        sandbox_type = session.sandbox_type

        if sandbox_type == SandboxType.TMUX:
            from .executors.tmux import TmuxExecutor

            return TmuxExecutor(session)

        elif sandbox_type == SandboxType.DOCKER:
            # Docker executor not yet implemented
            raise NotImplementedError(
                "Docker executor not yet implemented. Use TMUX for now."
            )

        elif sandbox_type == SandboxType.VM:
            raise NotImplementedError(
                "VM executor not yet implemented. Use TMUX for now."
            )

        else:
            raise ValueError(f"Unknown sandbox type: {sandbox_type}")

    @classmethod
    def create_sandbox(
        cls,
        organization: Account,
        *,
        config: SandboxConfig | None = None,
        project: Project | None = None,
        execution_run: ExecutionRun | None = None,
        name: str = "",
        user=None,
    ) -> tuple[SandboxSession, BaseSandboxExecutor]:
        """
        Create a new sandbox session and initialize it.

        Args:
            organization: The organization to create the sandbox for.
            config: Optional specific config to use (uses default if not provided).
            project: Optional project to associate with the sandbox.
            execution_run: Optional ExecutionRun this sandbox is for.
            name: Optional human-readable name for the session.
            user: Optional user creating the sandbox.

        Returns:
            Tuple of (SandboxSession, BaseSandboxExecutor).

        Raises:
            ValueError: If no suitable config is available.
            RuntimeError: If sandbox initialization fails.
        """
        # Get or find config
        if config is None:
            config = cls._get_default_config(organization)

        # Create session record
        with transaction.atomic():
            session = SandboxSession.objects.create(
                organization=organization,
                project=project,
                config=config,
                name=name or f"session-{config.name}",
                status=SessionStatus.CREATING,
                execution_run=execution_run,
                created_by=user,
                runtime_config={
                    "sandbox_type": config.sandbox_type,
                    "resource_limits": config.resource_limits,
                    "environment_variables": config.environment_variables,
                    "network_enabled": config.network_enabled,
                },
            )

        # Get executor and initialize
        try:
            executor = cls.get_executor(session)
            success = executor.initialize()

            if not success:
                raise RuntimeError(
                    f"Failed to initialize sandbox: {session.status_message}"
                )

            logger.info(
                f"Created sandbox session {session.session_id} "
                f"(type={config.sandbox_type}, org={organization.name})"
            )

            return session, executor

        except Exception as e:
            logger.exception(f"Error creating sandbox: {e}")
            session.set_status(SessionStatus.ERROR, str(e))
            raise

    @classmethod
    def get_session(
        cls,
        session_id: str,
        organization: Account,
    ) -> tuple[SandboxSession, BaseSandboxExecutor] | None:
        """
        Get an existing sandbox session and its executor.

        Args:
            session_id: The session UUID.
            organization: The organization (for security).

        Returns:
            Tuple of (SandboxSession, BaseSandboxExecutor) or None if not found.
        """
        try:
            session = SandboxSession.objects.get(
                session_id=session_id,
                organization=organization,
            )

            # Don't return terminated sessions
            if session.status == SessionStatus.TERMINATED:
                return None

            executor = cls.get_executor(session)
            return session, executor

        except SandboxSession.DoesNotExist:
            return None

    @classmethod
    def terminate_sandbox(
        cls,
        session: SandboxSession,
        *,
        cleanup_workspace: bool = False,
    ) -> bool:
        """
        Terminate a sandbox session.

        Args:
            session: The session to terminate.
            cleanup_workspace: Whether to delete the workspace directory.

        Returns:
            True if termination succeeded.
        """
        try:
            executor = cls.get_executor(session)
            success = executor.terminate()

            # Clean up workspace directory if requested and termination succeeded
            if cleanup_workspace and success and session.workspace_path:
                try:
                    import os

                    if os.path.exists(session.workspace_path):
                        shutil.rmtree(session.workspace_path)
                        logger.info(
                            f"Cleaned up workspace {session.workspace_path} "
                            f"for session {session.session_id}"
                        )
                except Exception as cleanup_error:
                    # Log but don't fail - termination already succeeded
                    logger.warning(
                        f"Failed to cleanup workspace {session.workspace_path}: {cleanup_error}"
                    )

            return success

        except Exception as e:
            logger.exception(f"Error terminating sandbox {session.session_id}: {e}")
            session.set_status(SessionStatus.ERROR, str(e))
            return False

    @classmethod
    def terminate_stale_sessions(
        cls,
        organization: Account | None = None,
        max_age_hours: int = 24,
    ) -> int:
        """
        Terminate sessions that have been inactive for too long.

        Args:
            organization: Optional org to scope cleanup to.
            max_age_hours: Maximum age in hours before termination.

        Returns:
            Number of sessions terminated.
        """
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=max_age_hours)

        queryset = SandboxSession.objects.filter(
            status__in=[SessionStatus.READY, SessionStatus.RUNNING],
            last_activity_at__lt=cutoff,
        )

        if organization:
            queryset = queryset.filter(organization=organization)

        terminated_count = 0
        for session in queryset:
            try:
                if cls.terminate_sandbox(session):
                    terminated_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to terminate stale session {session.session_id}: {e}"
                )

        logger.info(f"Terminated {terminated_count} stale sandbox sessions")
        return terminated_count

    @classmethod
    def _get_default_config(cls, organization: Account) -> SandboxConfig:
        """Get or create a default sandbox config for the organization."""
        # Try to find an existing default
        config = SandboxConfig.objects.filter(
            organization=organization,
            is_default=True,
        ).first()

        if config:
            return config

        # Try to find any config
        config = SandboxConfig.objects.filter(
            organization=organization,
        ).first()

        if config:
            return config

        # Create a default config
        config = SandboxConfig.objects.create(
            organization=organization,
            name="Default Tmux Sandbox",
            description="Auto-created default sandbox configuration",
            sandbox_type=SandboxType.TMUX,
            is_default=True,
            resource_limits={
                "timeout_seconds": 600,
                "max_output_size": 1048576,  # 1MB
            },
        )

        logger.info(
            f"Created default sandbox config for organization {organization.name}"
        )
        return config


def create_sandbox_for_execution(
    execution_run: ExecutionRun,
    *,
    config: SandboxConfig | None = None,
) -> tuple[SandboxSession, BaseSandboxExecutor]:
    """
    Convenience function to create a sandbox for an execution run.

    Args:
        execution_run: The ExecutionRun to create a sandbox for.
        config: Optional specific config to use.

    Returns:
        Tuple of (SandboxSession, BaseSandboxExecutor).
    """
    return SandboxManager.create_sandbox(
        organization=execution_run.organization,
        project=execution_run.project,
        execution_run=execution_run,
        config=config,
        name=f"exec-{str(execution_run.run_id)[:8]}",
        user=execution_run.created_by,
    )
