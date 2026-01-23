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
