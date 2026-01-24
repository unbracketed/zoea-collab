"""
Models for external agent configurations and execution records.

Provides:
- AgentType: Enum of supported external agent types
- ExternalAgentConfig: Configuration for connecting to external agents
- ExternalAgentRun: Record of agent execution
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings as django_settings
from django.db import models
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet


class AgentType(models.TextChoices):
    """Supported external agent types."""

    CLAUDE_CODE = "claude_code", "Claude Code"
    CODEX = "codex", "Codex (OpenAI)"
    OPENCODE = "opencode", "OpenCode"
    SHELLEY = "shelley", "Shelley"
    CUSTOM = "custom", "Custom CLI Agent"


class AgentRunStatus(models.TextChoices):
    """Status of an agent execution run."""

    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    TIMEOUT = "timeout", "Timed Out"


class ExternalAgentConfig(models.Model):
    """
    Configuration for an external coding agent.

    Stores connection settings, credentials, and default parameters
    for invoking external agents like Claude Code or Codex.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="external_agent_configs",
        help_text="The organization that owns this config",
    )

    # Basic configuration
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this agent configuration",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of this configuration's purpose",
    )

    agent_type = models.CharField(
        max_length=20,
        choices=AgentType.choices,
        help_text="Type of external agent",
    )

    is_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this agent configuration is active",
    )

    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default config for its type",
    )

    # Credentials (stored encrypted in production)
    credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="Agent-specific credentials (API keys, tokens)",
    )

    # Agent settings
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Agent-specific settings (model, temperature, etc.)",
    )

    # Default sandbox configuration
    default_sandbox = models.ForeignKey(
        "sandboxes.SandboxConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_agent_configs",
        help_text="Default sandbox config to use with this agent",
    )

    # Execution limits
    max_steps = models.PositiveIntegerField(
        default=50,
        help_text="Maximum steps/iterations per run",
    )

    timeout_seconds = models.PositiveIntegerField(
        default=600,
        help_text="Maximum execution time in seconds",
    )

    # CLI configuration
    cli_command = models.CharField(
        max_length=500,
        blank=True,
        help_text="Custom CLI command to invoke the agent",
    )

    cli_args = models.JSONField(
        default=list,
        blank=True,
        help_text="Default CLI arguments",
    )

    # Metadata
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_external_agent_configs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "External Agent Config"
        verbose_name_plural = "External Agent Configs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "agent_type"]),
            models.Index(fields=["organization", "is_default"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_agent_type_display()})"

    def get_credential(self, key: str, default: Any = None) -> Any:
        """Get a credential value."""
        return self.credentials.get(key, default)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def get_cli_command(self) -> str:
        """Get the CLI command for this agent type."""
        if self.cli_command:
            return self.cli_command

        # Default commands by agent type
        defaults = {
            AgentType.CLAUDE_CODE: "claude",
            AgentType.CODEX: "codex",
            AgentType.OPENCODE: "opencode",
            AgentType.SHELLEY: "shelley",
        }
        return defaults.get(self.agent_type, "")


class ExternalAgentRun(models.Model):
    """
    Record of an external agent execution.

    Tracks the prompt, response, resource usage, and any artifacts
    produced by the agent run.
    """

    # Unique identifier
    run_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique run identifier",
    )

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="external_agent_runs",
        help_text="The organization that owns this run",
    )

    # Optional project scope
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="external_agent_runs",
        null=True,
        blank=True,
        help_text="Project this run is associated with",
    )

    # Configuration used
    config = models.ForeignKey(
        ExternalAgentConfig,
        on_delete=models.SET_NULL,
        null=True,
        related_name="runs",
        help_text="Configuration used for this run",
    )

    # Sandbox session (if used)
    sandbox_session = models.ForeignKey(
        "sandboxes.SandboxSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_runs",
        help_text="Sandbox session this run executed in",
    )

    # Link to execution system
    execution_run = models.ForeignKey(
        "execution.ExecutionRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="external_agent_runs",
        help_text="Parent ExecutionRun if triggered by event",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=AgentRunStatus.choices,
        default=AgentRunStatus.PENDING,
        db_index=True,
    )

    status_message = models.TextField(
        blank=True,
        help_text="Status details or error message",
    )

    # Input
    prompt = models.TextField(
        help_text="The prompt sent to the agent",
    )

    system_prompt = models.TextField(
        blank=True,
        help_text="System prompt/instructions",
    )

    context_files = models.JSONField(
        default=list,
        blank=True,
        help_text="List of files provided as context",
    )

    # Output
    response = models.TextField(
        blank=True,
        help_text="The agent's response",
    )

    output_stream = models.TextField(
        blank=True,
        help_text="Full output stream (for CLI agents)",
    )

    # Artifacts produced
    artifacts = models.JSONField(
        default=list,
        blank=True,
        help_text="List of artifacts (files created/modified, etc.)",
    )

    # Resource usage
    tokens_used = models.JSONField(
        default=dict,
        blank=True,
        help_text="Token usage breakdown (prompt, completion, total)",
    )

    steps_taken = models.PositiveIntegerField(
        default=0,
        help_text="Number of steps/iterations taken",
    )

    # Runtime configuration (snapshot at execution time)
    runtime_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Runtime configuration snapshot",
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution started",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution completed",
    )

    # Owner
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_external_agent_runs",
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "External Agent Run"
        verbose_name_plural = "External Agent Runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["run_id"]),
        ]

    def __str__(self) -> str:
        agent_name = self.config.name if self.config else "unknown"
        return f"Run {str(self.run_id)[:8]} ({agent_name}: {self.status})"

    @property
    def agent_type(self) -> str:
        """Get the agent type from config."""
        if self.config:
            return self.config.agent_type
        return self.runtime_config.get("agent_type", AgentType.CUSTOM)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        delta = end_time - self.started_at
        return delta.total_seconds()

    def set_status(self, status: str, message: str = "") -> None:
        """Update the run status."""
        self.status = status
        self.status_message = message

        if status == AgentRunStatus.RUNNING:
            self.started_at = timezone.now()
        elif status in [
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
            AgentRunStatus.TIMEOUT,
        ]:
            self.completed_at = timezone.now()

        self.save(
            update_fields=["status", "status_message", "started_at", "completed_at"]
        )

    def add_artifact(self, artifact: dict) -> None:
        """Add an artifact to the run."""
        artifacts = list(self.artifacts)
        artifacts.append(artifact)
        self.artifacts = artifacts
        self.save(update_fields=["artifacts"])

    def update_tokens(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Update token usage."""
        current = dict(self.tokens_used)
        current["prompt_tokens"] = current.get("prompt_tokens", 0) + prompt_tokens
        current["completion_tokens"] = (
            current.get("completion_tokens", 0) + completion_tokens
        )
        current["total_tokens"] = (
            current["prompt_tokens"] + current["completion_tokens"]
        )
        self.tokens_used = current
        self.save(update_fields=["tokens_used"])
