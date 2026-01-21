"""
Workspace models with MPTT tree structure.

This module implements a hierarchical workspace model:
- Workspaces can exist in a tree structure using django-mptt
- Each workspace is scoped to a Project
- Workspaces are organization-scoped through their Project relationship
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mptt.models import MPTTModel, TreeForeignKey

from accounts.managers import OrganizationScopedQuerySet
from projects.email_utils import (
    slugify_for_email,
    generate_workspace_canonical_email,
    generate_alias_email,
    validate_email_alias,
)

User = get_user_model()


class WorkspaceQuerySet(OrganizationScopedQuerySet):
    """
    Organization-scoped queryset for workspaces.

    Provides filtering by organization through the project relationship.
    """

    def for_user(self, user):
        """Filter workspaces accessible to a user through their organization."""
        return self.filter(
            project__organization__organization_users__user=user
        ).distinct()

    def for_organization(self, organization):
        """Filter workspaces belonging to an organization."""
        return self.filter(project__organization=organization)


class Workspace(MPTTModel):
    """
    Hierarchical workspace model using MPTT.

    Workspaces organize content within a project and can form a tree structure
    for nested organization (e.g., folders, categories, or hierarchical workspaces).
    """

    # Project relationship (required - workspaces belong to projects)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='workspaces',
        help_text="The project this workspace belongs to"
    )

    # Required fields
    name = models.CharField(
        max_length=255,
        help_text="Workspace name"
    )
    slug = models.SlugField(
        max_length=100,
        blank=True,  # Allow blank for migration; save() auto-generates
        help_text="URL-friendly slug, auto-generated from name"
    )
    canonical_email = models.EmailField(
        max_length=254,
        unique=True,
        blank=True,  # Allow blank for migration; save() auto-generates
        help_text="Auto-generated canonical email address (e.g., workspace-slug.project-slug.org-slug@zoea.studio)"
    )
    email_alias = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="User-configurable email alias (e.g., 'support' -> support.org-slug@zoea.studio)"
    )

    # Optional fields
    description = models.TextField(
        blank=True,
        help_text="Workspace description"
    )

    # MPTT tree structure
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent workspace (null for root workspaces)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workspaces',
        help_text="User who created this workspace"
    )

    # Use organization-scoped queryset manager
    objects = WorkspaceQuerySet.as_manager()

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"
        unique_together = [['project', 'parent', 'name'], ['project', 'slug']]
        indexes = [
            models.Index(fields=['project']),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.name} (child of {self.parent.name})"
        return f"{self.name} (root)"

    def clean(self):
        """Validate email_alias format and uniqueness."""
        super().clean()
        if self.email_alias:
            # Normalize to lowercase
            self.email_alias = self.email_alias.lower()
            # Validate format
            if not validate_email_alias(self.email_alias):
                raise ValidationError({
                    'email_alias': 'Email alias must start with a letter, be 2-64 characters, '
                                   'and contain only lowercase letters, numbers, hyphens, or underscores.'
                })
            org = self.project.organization
            # Check for conflict with project slugs in the same org
            from projects.models import Project
            if Project.objects.filter(
                organization=org,
                slug=self.email_alias
            ).exists():
                raise ValidationError({
                    'email_alias': f'Email alias "{self.email_alias}" conflicts with an existing project slug.'
                })
            # Check for conflict with project aliases in the same org
            if Project.objects.filter(
                organization=org,
                email_alias=self.email_alias
            ).exists():
                raise ValidationError({
                    'email_alias': f'Email alias "{self.email_alias}" is already used by a project.'
                })
            # Check for conflict with other workspace aliases in the same org
            if Workspace.objects.filter(
                project__organization=org,
                email_alias=self.email_alias
            ).exclude(pk=self.pk).exists():
                raise ValidationError({
                    'email_alias': f'Email alias "{self.email_alias}" is already used by another workspace.'
                })

    def save(self, *args, **kwargs):
        """Auto-generate slug and canonical_email from name if not set."""
        if not self.slug:
            base_slug = slugify_for_email(self.name)
            slug = base_slug
            counter = 1
            # Handle duplicates within the project
            while Workspace.objects.filter(
                project=self.project,
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        # Always regenerate canonical_email from slug (in case slug or project changed)
        self.canonical_email = generate_workspace_canonical_email(
            self.slug, self.project.slug, self.project.organization.slug
        )
        super().save(*args, **kwargs)

    def get_organization(self):
        """Get the organization this workspace belongs to through its project."""
        return self.project.organization

    def get_full_path(self):
        """
        Get the full path of this workspace from root to current.

        Returns:
            str: Path like "Root / Child / Grandchild"
        """
        ancestors = self.get_ancestors(include_self=True)
        return " / ".join([ws.name for ws in ancestors])

    @property
    def alias_email(self):
        """Return the full alias email address, or None if no alias set."""
        if not self.email_alias:
            return None
        return generate_alias_email(self.email_alias, self.project.organization.slug)
