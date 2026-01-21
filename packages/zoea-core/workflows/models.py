import uuid

from django.contrib.auth import get_user_model
from django.db import models

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class Workflow(models.Model):
    """
    Organization-scoped workflow model.

    Workflows define automated or semi-automated processes with associated metadata.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='workflows',
        help_text="The organization that owns this workflow"
    )

    # Required fields
    name = models.CharField(
        max_length=255,
        help_text="Workflow name"
    )

    # Optional fields
    description = models.TextField(
        blank=True,
        help_text="Workflow description"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional workflow metadata and configuration"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workflows',
        help_text="User who created this workflow"
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Workflow"
        verbose_name_plural = "Workflows"
        ordering = ['-created_at']
        unique_together = [['organization', 'name']]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class WorkflowRun(models.Model):
    """
    Tracks individual workflow execution runs.

    Records inputs, outputs, timing, and status for each workflow execution,
    enabling history viewing and debugging.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="workflow_runs",
        help_text="The organization that owns this workflow run",
    )

    # Workflow reference (slug-based, not FK to allow builtin workflows)
    workflow_slug = models.CharField(
        max_length=100,
        help_text="Slug of the workflow that was executed",
    )

    # Unique run identifier
    run_id = models.CharField(
        max_length=36,
        unique=True,
        default=uuid.uuid4,
        help_text="Unique identifier for this execution run",
    )

    # Execution status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Current execution status",
    )

    # Input/Output data
    inputs = models.JSONField(
        default=dict,
        help_text="Input parameters provided to the workflow",
    )
    outputs = models.JSONField(
        null=True,
        blank=True,
        help_text="Output results from the workflow execution",
    )
    error = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if execution failed",
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution actually started",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution completed (success or failure)",
    )

    # Context references
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="workflow_runs",
        help_text="User who initiated this run",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="workflow_runs",
        help_text="Project context for this run",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="workflow_runs",
        help_text="Workspace context for this run",
    )

    # AI provider tracking
    provider_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="AI provider and model used (e.g., 'openai/gpt-4o')",
    )
    token_usage = models.JSONField(
        null=True,
        blank=True,
        help_text="Token usage breakdown (input_tokens, output_tokens, etc.)",
    )

    # Django-Q2 task tracking
    task_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django-Q2 task ID for background execution",
    )

    # Artifacts collection for workflow outputs
    artifacts = models.ForeignKey(
        'documents.DocumentCollection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_runs',
        help_text="Collection of artifacts (documents, files, etc.) produced by this workflow"
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Workflow Run"
        verbose_name_plural = "Workflow Runs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "workflow_slug"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.workflow_slug} run {self.run_id[:8]} ({self.status})"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def get_or_create_artifacts(self):
        """
        Get or lazily create the artifacts collection for this workflow run.

        Creates a DocumentCollection with collection_type='artifact' if one
        doesn't exist. The collection is scoped to the workflow run's
        organization and workspace.

        Returns:
            DocumentCollection: The artifacts collection for this workflow run.
        """
        if self.artifacts_id:
            return self.artifacts

        from documents.models import DocumentCollection, CollectionType

        collection = DocumentCollection.objects.create(
            organization=self.organization,
            workspace=self.workspace,
            collection_type=CollectionType.ARTIFACT,
            name=f"Workflow: {self.workflow_slug} ({self.run_id[:8]})",
            created_by=self.created_by,
        )
        self.artifacts = collection
        self.save(update_fields=['artifacts'])
        return collection
