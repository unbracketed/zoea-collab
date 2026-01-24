"""
Models for output routing configuration.

Provides:
- DestinationType: Enum of supported output destinations
- OutputRoute: Configuration for routing outputs to destinations
- DispatchLog: Log of dispatch attempts
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet


class DestinationType(models.TextChoices):
    """Supported output destination types."""

    SLACK = "slack", "Slack"
    DISCORD = "discord", "Discord"
    WEBHOOK = "webhook", "Webhook"
    DOCUMENT = "document", "Document"
    EMAIL = "email", "Email"
    PLATFORM_REPLY = "platform_reply", "Reply to Platform"


class DispatchStatus(models.TextChoices):
    """Status of a dispatch attempt."""

    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class OutputRoute(models.Model):
    """
    Configuration for routing outputs to a destination.

    Routes can be associated with:
    - Event triggers (outputs dispatched after trigger execution)
    - Projects (default routes for project outputs)
    - Organization (default routes for all outputs)
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="output_routes",
        help_text="The organization that owns this route",
    )

    # Basic configuration
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this route",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of this route's purpose",
    )

    destination_type = models.CharField(
        max_length=20,
        choices=DestinationType.choices,
        help_text="Type of output destination",
    )

    is_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this route is active",
    )

    # Scope
    trigger = models.ForeignKey(
        "events.EventTrigger",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="output_routes",
        help_text="If set, route is used for this trigger's outputs",
    )

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="output_routes",
        help_text="If set, route is default for this project",
    )

    # Platform connection (for Slack, Discord, Platform Reply)
    platform_connection = models.ForeignKey(
        "platform_adapters.PlatformConnection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="output_routes",
        help_text="Platform connection to use for output",
    )

    # Destination configuration
    channel_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Channel/room ID for Slack/Discord",
    )

    webhook_url = models.URLField(
        blank=True,
        help_text="Webhook URL for webhook destinations",
    )

    # Template configuration
    template = models.TextField(
        blank=True,
        help_text="Output template (supports Jinja2-style variables)",
    )

    include_artifacts = models.BooleanField(
        default=True,
        help_text="Whether to include artifacts in the output",
    )

    format_type = models.CharField(
        max_length=20,
        default="text",
        help_text="Output format: text, json, markdown",
    )

    # Document destination config
    document_folder = models.ForeignKey(
        "documents.Folder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="output_routes",
        help_text="Folder to create documents in",
    )

    document_name_template = models.CharField(
        max_length=255,
        blank=True,
        default="output_{timestamp}",
        help_text="Template for document names",
    )

    # Filtering
    output_filter = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter criteria for which outputs to dispatch",
    )

    # Priority for ordering when multiple routes match
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority routes are executed first",
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_output_routes",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Output Route"
        verbose_name_plural = "Output Routes"
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "destination_type"]),
            models.Index(fields=["organization", "is_enabled"]),
            models.Index(fields=["trigger", "is_enabled"]),
            models.Index(fields=["project", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_destination_type_display()})"

    def matches_output(self, output_data: dict) -> bool:
        """
        Check if this route matches the given output data.

        Args:
            output_data: Dict with output information.

        Returns:
            True if the route should handle this output.
        """
        if not self.is_enabled:
            return False

        if not self.output_filter:
            return True

        # Check filter conditions
        for key, expected in self.output_filter.items():
            actual = output_data.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False

        return True


class DispatchLog(models.Model):
    """
    Log of output dispatch attempts.

    Records each attempt to send output to a destination
    for debugging and auditing.
    """

    # Unique identifier
    dispatch_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # Organization relationship
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="dispatch_logs",
    )

    # Route used
    route = models.ForeignKey(
        OutputRoute,
        on_delete=models.SET_NULL,
        null=True,
        related_name="dispatch_logs",
    )

    # Source of the output
    execution_run = models.ForeignKey(
        "execution.ExecutionRun",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="dispatch_logs",
    )

    agent_run = models.ForeignKey(
        "agent_wrappers.ExternalAgentRun",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="dispatch_logs",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=DispatchStatus.choices,
        default=DispatchStatus.PENDING,
        db_index=True,
    )

    status_message = models.TextField(
        blank=True,
        help_text="Status details or error message",
    )

    # Dispatch details
    destination_type = models.CharField(
        max_length=20,
        choices=DestinationType.choices,
    )

    destination_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Destination details (channel, URL, etc.)",
    )

    # Payload
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="The payload that was/will be sent",
    )

    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response from the destination",
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the dispatch was sent",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the dispatch completed",
    )

    # Retries
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts",
    )

    class Meta:
        verbose_name = "Dispatch Log"
        verbose_name_plural = "Dispatch Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["route", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"Dispatch {str(self.dispatch_id)[:8]} ({self.destination_type}: {self.status})"

    def set_status(self, status: str, message: str = "") -> None:
        """Update the dispatch status."""
        self.status = status
        self.status_message = message

        if status == DispatchStatus.SENDING:
            self.sent_at = timezone.now()
        elif status in [DispatchStatus.SUCCESS, DispatchStatus.FAILED]:
            self.completed_at = timezone.now()

        self.save(update_fields=["status", "status_message", "sent_at", "completed_at"])

    @property
    def duration_ms(self) -> int | None:
        """Calculate dispatch duration in milliseconds."""
        if not self.sent_at or not self.completed_at:
            return None
        delta = self.completed_at - self.sent_at
        return int(delta.total_seconds() * 1000)
