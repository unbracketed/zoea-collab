"""Unified execution run model for events and workflows."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class ExecutionRun(models.Model):
    """Tracks execution of triggers, workflows, and agent runs."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="execution_runs",
        help_text="Organization that owns this run",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="execution_runs",
        null=True,
        blank=True,
        help_text="Optional project scope",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="execution_runs",
        null=True,
        blank=True,
        help_text="Optional workspace scope",
    )
    channel = models.ForeignKey(
        "channels.Channel",
        on_delete=models.SET_NULL,
        related_name="execution_runs",
        null=True,
        blank=True,
        help_text="Optional channel context",
    )
    trigger = models.ForeignKey(
        "events.EventTrigger",
        on_delete=models.SET_NULL,
        related_name="execution_runs",
        null=True,
        blank=True,
        help_text="Optional trigger that initiated this run",
    )

    run_id = models.CharField(
        max_length=36,
        unique=True,
        default=uuid.uuid4,
        help_text="Unique identifier for this execution run",
    )

    trigger_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Normalized trigger type (chat_message, email_received, etc.)",
    )
    source_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of source that triggered this run",
    )
    source_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of the source object that triggered this run",
    )

    workflow_slug = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Workflow slug executed in this run",
    )
    graph_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="LangGraph graph identifier",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current execution status",
    )

    input_envelope = models.JSONField(
        default=dict,
        blank=True,
        help_text="Normalized trigger envelope",
    )
    inputs = models.JSONField(
        default=dict,
        help_text="Input parameters provided to the run",
    )
    outputs = models.JSONField(
        null=True,
        blank=True,
        help_text="Output results from execution",
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if execution failed",
    )
    telemetry = models.JSONField(
        null=True,
        blank=True,
        help_text="Execution telemetry (token usage, timing, steps)",
    )

    provider_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="AI provider/model used (e.g., 'openai/gpt-4o')",
    )
    token_usage = models.JSONField(
        null=True,
        blank=True,
        help_text="Token usage breakdown",
    )

    task_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Background task ID",
    )

    artifacts = models.ForeignKey(
        "documents.DocumentCollection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_runs",
        help_text="Artifacts produced by this run",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_runs",
        help_text="User who initiated this run",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Execution Run"
        verbose_name_plural = "Execution Runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "trigger_type"]),
            models.Index(fields=["workflow_slug", "created_at"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def __str__(self):
        return f"Run {self.run_id[:8]} ({self.status})"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def get_or_create_artifacts(self):
        if self.artifacts_id:
            return self.artifacts

        from documents.models import CollectionType, DocumentCollection
        from workspaces.models import Workspace

        workspace = self.workspace
        if workspace is None and self.project_id:
            workspace = Workspace.objects.filter(project_id=self.project_id).first()

        collection = DocumentCollection.objects.create(
            organization=self.organization,
            workspace=workspace,
            collection_type=CollectionType.ARTIFACT,
            name=f"Execution Run {self.run_id[:8]}",
            created_by=self.created_by,
        )
        self.artifacts = collection
        self.save(update_fields=["artifacts"])
        return collection
