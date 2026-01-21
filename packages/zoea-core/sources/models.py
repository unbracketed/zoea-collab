"""
Django models for document sources.

This module defines the Source model which stores configuration for
different document storage backends (local filesystem, S3, R2, etc.).
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.managers import OrganizationScopedQuerySet
from .registry import SourceRegistry
from .base import SourceInterface

User = get_user_model()


class SourceQuerySet(OrganizationScopedQuerySet):
    """Organization-scoped queryset for sources."""

    def for_project(self, project):
        """Filter sources by project."""
        return self.filter(project=project)

    def active(self):
        """Filter to only active sources."""
        return self.filter(is_active=True)


class Source(models.Model):
    """
    Document source configuration.

    A source represents a location where documents are stored (local filesystem,
    S3 bucket, R2 bucket, etc.). Each project can have multiple sources, and
    the system will pull documents from all active sources when syncing.

    Multi-tenant scoping:
        Sources are scoped to both an organization and a project. The organization
        is denormalized from the project for efficient querying.

    Configuration:
        The config field stores source-specific configuration as JSON. Each source
        type defines its own config schema. See source implementations for details.

    Example:
        # Local filesystem source
        Source.objects.create(
            project=project,
            organization=project.organization,
            source_type='local',
            name='Demo Documents',
            config={
                'path': '/Users/brian/projects/demo-docs',
                'pattern': '**/*.{md,pdf,png}'
            }
        )

        # S3 source
        Source.objects.create(
            project=project,
            organization=project.organization,
            source_type='s3',
            name='Production Documents',
            config={
                'bucket': 'my-documents',
                'prefix': 'project-files/',
                'region': 'us-west-2',
                'access_key_id': '...',
                'secret_access_key': '...'
            }
        )
    """

    SOURCE_TYPE_CHOICES = [
        ('local', 'Local File System'),
        ('s3', 'AWS S3'),
        ('r2', 'Cloudflare R2'),
    ]

    # Multi-tenant relationships
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='sources',
        help_text="Organization that owns this source"
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='sources',
        help_text="Project this source belongs to"
    )

    # Source configuration
    source_type = models.CharField(
        max_length=50,
        choices=SOURCE_TYPE_CHOICES,
        help_text="Type of document source"
    )
    name = models.CharField(
        max_length=200,
        help_text="Display name for this source"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of this source"
    )
    config = models.JSONField(
        help_text="Source-specific configuration (schema depends on source_type)"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this source is actively used for document syncing"
    )
    last_sync_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time documents were synced from this source"
    )
    last_test_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time connection was tested"
    )
    last_test_success = models.BooleanField(
        blank=True,
        null=True,
        help_text="Result of last connection test"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sources',
        help_text="User who created this source"
    )

    # Use organization-scoped queryset manager
    objects = SourceQuerySet.as_manager()

    class Meta:
        verbose_name = "Source"
        verbose_name_plural = "Sources"
        ordering = ['name']
        unique_together = [['project', 'name']]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['project', 'is_active']),
            models.Index(fields=['source_type']),
        ]

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.name} ({self.source_type}, {status})"

    def clean(self):
        """
        Validate the source configuration.

        This method validates:
        1. Organization matches the project's organization
        2. Source type is registered
        3. Source configuration is valid for the source type

        Raises:
            ValidationError: If validation fails.
        """
        super().clean()

        # Validate organization matches project
        if self.project and self.organization_id != self.project.organization_id:
            raise ValidationError({
                'organization': "Source organization must match project's organization"
            })

        # Validate source type is registered
        if not SourceRegistry.is_registered(self.source_type):
            available = ', '.join(sorted(SourceRegistry.get_registered_types().keys()))
            raise ValidationError({
                'source_type': f"Unknown source type '{self.source_type}'. Available: {available}"
            })

        # Validate source configuration (skip only if config is None)
        if self.config is not None:
            try:
                source_class = SourceRegistry.get(self.source_type)
                source_class(self.config)  # This will call validate_config()
            except ValueError as e:
                raise ValidationError({
                    'config': f"Invalid configuration for {self.source_type} source: {e}"
                })

    def save(self, *args, **kwargs):
        """
        Save the source.

        Auto-populates organization from project if not set.
        """
        # Auto-populate organization from project
        if self.project and not self.organization_id:
            self.organization = self.project.organization

        super().save(*args, **kwargs)

    def get_source_instance(self) -> SourceInterface:
        """
        Get configured source implementation instance.

        Returns:
            Configured source instance ready to use.

        Raises:
            ValueError: If source type is not registered or config is invalid.

        Example:
            source_record = Source.objects.get(name='My Source')
            source = source_record.get_source_instance()

            for doc_meta in source.list_documents():
                content = source.read_document(doc_meta.path)
                print(f"Read {doc_meta.name}")
        """
        source_class = SourceRegistry.get(self.source_type)
        return source_class(self.config)

    def test_connection(self) -> bool:
        """
        Test if the source is accessible with current configuration.

        This method creates a source instance and tests the connection,
        updating the last_test_at and last_test_success fields.

        Returns:
            True if connection is successful, False otherwise.

        Example:
            source = Source.objects.get(name='My Source')
            if source.test_connection():
                print("Connection successful!")
            else:
                print("Connection failed!")
        """
        from django.utils import timezone

        try:
            source = self.get_source_instance()
            success = source.test_connection()

            # Update test status
            self.last_test_at = timezone.now()
            self.last_test_success = success
            self.save(update_fields=['last_test_at', 'last_test_success'])

            return success

        except Exception:
            # Update test status
            self.last_test_at = timezone.now()
            self.last_test_success = False
            self.save(update_fields=['last_test_at', 'last_test_success'])

            return False

    def get_display_name(self) -> str:
        """
        Get the source's display name from the implementation.

        Returns:
            Human-readable source description.
        """
        try:
            source = self.get_source_instance()
            return source.get_display_name()
        except Exception:
            return f"{self.name} (error: cannot create source instance)"
