from django.db import models
from django.contrib.auth import get_user_model
from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class ToolCategory(models.TextChoices):
    """Categories for organizing tools."""

    SEARCH = "search", "Search"
    IMAGE = "image", "Image Generation"
    DOCUMENT = "document", "Document Processing"
    ANALYSIS = "analysis", "Analysis"
    CODE = "code", "Code Execution"
    DATA = "data", "Data Extraction"


class ProjectToolConfig(models.Model):
    """
    Per-project tool enablement configuration.

    Each record represents whether a specific tool is enabled for a project.
    Tools not explicitly configured default to their global enabled state
    as defined in the ToolRegistry.

    Example:
        # Disable web_search for a specific project
        config = ProjectToolConfig.objects.create(
            organization=org,
            project=project,
            tool_name="web_search",
            is_enabled=False,
            created_by=user,
        )
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="tool_configs",
        help_text="Organization that owns this configuration",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tool_configs",
        help_text="Project this configuration applies to",
    )

    # Tool identification
    tool_name = models.CharField(
        max_length=100,
        help_text="Unique tool identifier from ToolRegistry (e.g., 'web_search')",
    )

    # Configuration
    is_enabled = models.BooleanField(
        default=True, help_text="Whether this tool is enabled for the project"
    )
    config_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tool-specific configuration overrides (JSON)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tool_configs",
    )

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Project Tool Configuration"
        verbose_name_plural = "Project Tool Configurations"
        unique_together = [["project", "tool_name"]]
        indexes = [
            models.Index(fields=["project", "is_enabled"]),
        ]

    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"{self.tool_name} ({status}) - {self.project.name}"


class ToolExecutionLog(models.Model):
    """
    Audit log for tool executions.

    Tracks tool usage for analytics, debugging, and rate limiting.
    This log captures every tool invocation with sanitized input/output.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="tool_executions",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tool_executions",
        null=True,
        blank=True,
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="tool_executions",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="tool_executions",
    )

    # Execution details
    tool_name = models.CharField(max_length=100)
    agent_name = models.CharField(max_length=100, blank=True)
    input_summary = models.JSONField(
        default=dict, help_text="Sanitized summary of input parameters"
    )
    output_summary = models.JSONField(
        default=dict, help_text="Sanitized summary of output"
    )

    # Performance metrics
    duration_ms = models.IntegerField(null=True, help_text="Execution time in ms")
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    # Timestamps
    executed_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Tool Execution Log"
        verbose_name_plural = "Tool Execution Logs"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["organization", "tool_name", "-executed_at"]),
            models.Index(fields=["project", "-executed_at"]),
        ]

    def __str__(self):
        return f"{self.tool_name} @ {self.executed_at}"
