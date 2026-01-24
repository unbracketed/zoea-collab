"""
Event trigger models for workflow automation.

Provides event-based triggers that execute Agent Skills when events occur
(e.g., email received, document created), as well as scheduled events that
run at specific times or on recurring cron schedules.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class EventType(models.TextChoices):
    """Supported event types for triggers."""

    # Existing
    EMAIL_RECEIVED = "email_received", "Email Received"
    DOCUMENT_CREATED = "document_created", "Document Created"
    DOCUMENT_UPDATED = "document_updated", "Document Updated"
    DOCUMENTS_SELECTED = "documents_selected", "Documents Selected"

    # Messaging (from platform adapters)
    CHAT_MESSAGE = "chat_message", "Chat Message"
    SLACK_MESSAGE = "slack_message", "Slack Message"
    DISCORD_MESSAGE = "discord_message", "Discord Message"

    # Webhooks
    WEBHOOK_RECEIVED = "webhook_received", "Webhook Received"
    NOTION_PAGE_UPDATED = "notion_page_updated", "Notion Page Updated"

    # Scheduled (for future ScheduledEvent support)
    SCHEDULED_ONESHOT = "scheduled_oneshot", "Scheduled One-Shot"
    SCHEDULED_CRON = "scheduled_cron", "Scheduled Recurring"

    # System
    AGENT_COMPLETED = "agent_completed", "Agent Completed"


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


class ScheduleType(models.TextChoices):
    """Types of scheduled events."""

    ONESHOT = "oneshot", "One-Shot"
    CRON = "cron", "Recurring (Cron)"


class ScheduledEvent(models.Model):
    """
    Scheduled event configuration for time-based trigger execution.

    Supports two modes:
    - One-shot: Execute once at a specific time (scheduled_at)
    - Cron: Execute on a recurring schedule (cron_expression)

    When a scheduled event fires, it dispatches the configured event_type
    to the associated EventTrigger for processing.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="scheduled_events",
        help_text="The organization that owns this scheduled event",
    )

    # Associated trigger to execute
    trigger = models.ForeignKey(
        EventTrigger,
        on_delete=models.CASCADE,
        related_name="scheduled_events",
        help_text="The event trigger to execute when this schedule fires",
    )

    # Schedule configuration
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this scheduled event",
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of what this scheduled event does",
    )

    schedule_type = models.CharField(
        max_length=10,
        choices=ScheduleType.choices,
        help_text="Type of schedule: one-shot or recurring cron",
    )

    # One-shot scheduling
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="For one-shot events: when to execute (UTC)",
    )

    # Cron scheduling
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        help_text="For cron events: cron expression (e.g., '0 9 * * 1-5' for weekdays at 9am)",
    )

    timezone_name = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Timezone for interpreting the schedule (e.g., 'America/New_York')",
    )

    # Event data to pass when triggered
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data to include in the event payload",
    )

    # Status
    is_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this scheduled event is active",
    )

    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Calculated next execution time (for scheduling queries)",
    )

    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this event last fired",
    )

    run_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times this event has fired",
    )

    # For Django-Q2 integration
    django_q_schedule_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID of the Django-Q2 schedule (if using cron)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_scheduled_events",
        help_text="User who created this scheduled event",
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Scheduled Event"
        verbose_name_plural = "Scheduled Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_enabled"]),
            models.Index(fields=["schedule_type", "is_enabled"]),
            models.Index(fields=["next_run_at"]),
        ]

    def __str__(self):
        schedule_info = (
            self.cron_expression
            if self.schedule_type == ScheduleType.CRON
            else str(self.scheduled_at)
        )
        return f"{self.name} ({self.schedule_type}: {schedule_info})"

    def record_execution(self) -> None:
        """Record that this scheduled event was executed."""
        self.last_run_at = timezone.now()
        self.run_count = models.F("run_count") + 1
        self.save(update_fields=["last_run_at", "run_count"])

    def calculate_next_run(self) -> None:
        """Calculate and update the next run time based on schedule type."""
        if not self.is_enabled:
            self.next_run_at = None
        elif self.schedule_type == ScheduleType.ONESHOT:
            # One-shot: next_run is scheduled_at if in future, else None
            if self.scheduled_at and self.scheduled_at > timezone.now():
                self.next_run_at = self.scheduled_at
            else:
                self.next_run_at = None
        elif self.schedule_type == ScheduleType.CRON and self.cron_expression:
            # Cron: calculate next occurrence from expression
            self.next_run_at = self._calculate_next_cron_run()

        self.save(update_fields=["next_run_at"])

    def _calculate_next_cron_run(self):
        """Calculate the next cron execution time."""
        try:
            from croniter import croniter
            import pytz

            tz = pytz.timezone(self.timezone_name)
            now = timezone.now().astimezone(tz)
            cron = croniter(self.cron_expression, now)
            return cron.get_next(ret_type=timezone.datetime)
        except ImportError:
            # croniter not installed, return None
            return None
        except Exception:
            # Invalid cron expression or timezone
            return None
