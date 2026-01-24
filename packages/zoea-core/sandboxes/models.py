"""
Models for sandbox configurations and sessions.

Provides:
- SandboxType: Enum of supported sandbox types (tmux, docker, vm)
- SandboxConfig: Template for creating sandboxes
- SandboxSession: Active execution environment
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet


class SandboxType(models.TextChoices):
    """Supported sandbox execution environment types."""

    TMUX = "tmux", "Tmux Session"
    DOCKER = "docker", "Docker Container"
    VM = "vm", "Virtual Machine"


class SessionStatus(models.TextChoices):
    """Status of a sandbox session."""

    PENDING = "pending", "Pending Creation"
    CREATING = "creating", "Creating"
    READY = "ready", "Ready"
    RUNNING = "running", "Running"
    ERROR = "error", "Error"
    TERMINATED = "terminated", "Terminated"


class SandboxConfig(models.Model):
    """
    Template configuration for creating sandboxes.

    Defines the type of sandbox, resource limits, allowed paths,
    and environment settings. Configs are organization-scoped and
    can be reused across multiple sessions.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="sandbox_configs",
        help_text="The organization that owns this config",
    )

    # Basic configuration
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this sandbox configuration",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of this configuration's purpose",
    )

    sandbox_type = models.CharField(
        max_length=20,
        choices=SandboxType.choices,
        default=SandboxType.TMUX,
        help_text="Type of execution environment",
    )

    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default config for the organization",
    )

    # Docker-specific settings
    docker_image = models.CharField(
        max_length=500,
        blank=True,
        default="python:3.12-slim",
        help_text="Docker image to use (for docker sandbox type)",
    )

    # Resource limits
    resource_limits = models.JSONField(
        default=dict,
        blank=True,
        help_text="Resource limits (cpu, memory, disk, timeout_seconds)",
    )

    # Path configuration
    allowed_paths = models.JSONField(
        default=list,
        blank=True,
        help_text="List of paths the sandbox can access",
    )

    workspace_base_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Base directory for sandbox workspaces",
    )

    # Environment configuration
    environment_variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Environment variables to set in the sandbox",
    )

    shell_command = models.CharField(
        max_length=255,
        default="/bin/bash",
        help_text="Default shell to use",
    )

    # Security settings
    network_enabled = models.BooleanField(
        default=True,
        help_text="Whether network access is allowed",
    )

    mount_project_readonly = models.BooleanField(
        default=False,
        help_text="Mount project directory as read-only",
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sandbox_configs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Sandbox Configuration"
        verbose_name_plural = "Sandbox Configurations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "sandbox_type"]),
            models.Index(fields=["organization", "is_default"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_sandbox_type_display()})"

    def get_resource_limit(self, key: str, default: Any = None) -> Any:
        """Get a specific resource limit value."""
        return self.resource_limits.get(key, default)

    def get_timeout_seconds(self) -> int:
        """Get the timeout in seconds, defaulting to 10 minutes."""
        return self.get_resource_limit("timeout_seconds", 600)


class SandboxSession(models.Model):
    """
    Active sandbox execution environment.

    Represents a running or completed sandbox instance where
    agents can execute code and interact with files.
    """

    # Unique identifier
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique session identifier",
    )

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="sandbox_sessions",
        help_text="The organization that owns this session",
    )

    # Optional project scope
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="sandbox_sessions",
        null=True,
        blank=True,
        help_text="Project this session is associated with",
    )

    # Configuration used
    config = models.ForeignKey(
        SandboxConfig,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sessions",
        help_text="Configuration used to create this session",
    )

    # Session name for identification
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable session name",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.PENDING,
        db_index=True,
    )

    status_message = models.TextField(
        blank=True,
        help_text="Details about the current status (e.g., error message)",
    )

    # Runtime identifiers (depends on sandbox type)
    container_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Docker container ID (for docker type)",
    )

    tmux_session_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Tmux session name (for tmux type)",
    )

    vm_instance_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="VM instance ID (for vm type)",
    )

    # Workspace
    workspace_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to the session's workspace directory",
    )

    # Runtime configuration (snapshot of config at creation time)
    runtime_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Runtime configuration (frozen from config at creation)",
    )

    # Execution tracking
    execution_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of commands executed in this session",
    )

    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last activity occurred",
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the sandbox became ready",
    )
    terminated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the sandbox was terminated",
    )

    # Owner
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sandbox_sessions",
    )

    # Link to execution system
    execution_run = models.ForeignKey(
        "execution.ExecutionRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sandbox_sessions",
        help_text="ExecutionRun this session was created for",
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Sandbox Session"
        verbose_name_plural = "Sandbox Sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["session_id"]),
        ]

    def __str__(self) -> str:
        name = self.name or str(self.session_id)[:8]
        return f"Session {name} ({self.status})"

    @property
    def sandbox_type(self) -> str:
        """Get the sandbox type from config or runtime_config."""
        if self.config:
            return self.config.sandbox_type
        return self.runtime_config.get("sandbox_type", SandboxType.TMUX)

    def set_status(self, status: str, message: str = "") -> None:
        """Update the session status."""
        self.status = status
        self.status_message = message

        if status == SessionStatus.READY:
            self.started_at = timezone.now()
        elif status == SessionStatus.TERMINATED:
            self.terminated_at = timezone.now()

        self.save(
            update_fields=["status", "status_message", "started_at", "terminated_at"]
        )

    def record_activity(self) -> None:
        """Record that activity occurred in this session."""
        self.last_activity_at = timezone.now()
        self.execution_count = models.F("execution_count") + 1
        self.save(update_fields=["last_activity_at", "execution_count"])

    @property
    def duration_seconds(self) -> float | None:
        """Calculate session duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.terminated_at or timezone.now()
        delta = end_time - self.started_at
        return delta.total_seconds()

    def get_runtime_identifier(self) -> str:
        """Get the runtime identifier based on sandbox type."""
        sandbox_type = self.sandbox_type
        if sandbox_type == SandboxType.DOCKER:
            return self.container_id
        elif sandbox_type == SandboxType.TMUX:
            return self.tmux_session_name
        elif sandbox_type == SandboxType.VM:
            return self.vm_instance_id
        return ""
