"""
Event trigger models for workflow automation.

Provides event-based triggers that execute Agent Skills when events occur
(e.g., email received, document created).
"""

from django.contrib.auth import get_user_model
from django.db import models

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class EventType(models.TextChoices):
    """Supported event types for triggers."""

    EMAIL_RECEIVED = "email_received", "Email Received"
    DOCUMENT_CREATED = "document_created", "Document Created"
    DOCUMENT_UPDATED = "document_updated", "Document Updated"
    DOCUMENTS_SELECTED = "documents_selected", "Documents Selected"


class EventTrigger(models.Model):
    """
    Configuration for event-based skill execution.

    When an event of the specified type occurs, the configured skills are
    loaded and executed to process the event data.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="event_triggers",
        help_text="The organization that owns this trigger",
    )

    # Optional project scope (None = org-wide trigger)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="event_triggers",
        null=True,
        blank=True,
        help_text="Optional project scope. If not set, trigger applies to entire organization.",
    )

    # Trigger configuration
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this trigger",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of what this trigger does",
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
        help_text="Type of event that activates this trigger",
    )

    # Skills to execute (list of skill names from SkillRegistry)
    skills = models.JSONField(
        default=list,
        help_text="List of skill names to execute when triggered (e.g., ['extract-data', 'send-webhook'])",
    )

    # Execution configuration
    is_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this trigger is active",
    )
    run_async = models.BooleanField(
        default=True,
        help_text="Execute in background task (recommended for production)",
    )

    # Optional filters for more specific event matching
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional filters for event matching (e.g., {'document_type': 'markdown'})",
    )

    # Additional configuration passed to SkillsAgentService
    agent_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional configuration for the agent (e.g., custom instructions, max_steps)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_event_triggers",
        help_text="User who created this trigger",
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Event Trigger"
        verbose_name_plural = "Event Triggers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "event_type", "is_enabled"]),
            models.Index(fields=["project", "event_type", "is_enabled"]),
        ]

    def __str__(self):
        scope = self.project.name if self.project else "org-wide"
        return f"{self.name} ({self.event_type}) - {scope}"

    @property
    def skill_count(self) -> int:
        """Return the number of skills configured for this trigger."""
        return len(self.skills) if self.skills else 0
