from django.db import models
from django.contrib.auth import get_user_model
from accounts.managers import OrganizationScopedQuerySet
from django.core.exceptions import ValidationError
from projects.email_utils import (
    slugify_for_email,
    generate_project_canonical_email,
    generate_alias_email,
    validate_email_alias,
    get_email_domain,
)

User = get_user_model()


# Color theme choices matching shadcn.io themes in frontend/src/styles/shadcn-themes.css
THEME_CHOICES = [
    ('amber-minimal', 'Amber Minimal'),
    ('claude', 'Claude'),
    ('corporate', 'Corporate'),
    ('modern-minimal', 'Modern'),
    ('nature', 'Nature'),
    ('slack', 'Slack'),
    ('twitter', 'Twitter'),
    ('cyberpunk', 'Cyberpunk'),
    ('red', 'Red'),
    ('summer', 'Summer'),
    ('notebook', 'Notebook'),
]

# Map theme names to primary colors for UI elements (approximate hex from OKLCH)
THEME_COLORS = {
    'amber-minimal': '#d4a259',
    'claude': '#c75f2a',
    'corporate': '#2563eb',
    'modern-minimal': '#7c3aed',
    'nature': '#059669',
    'slack': '#611f69',
    'twitter': '#1d9bf0',
    'cyberpunk': '#e11d48',
    'red': '#dc2626',
    'summer': '#ea580c',
    'notebook': '#3b82f6',
}


class Project(models.Model):
    """
    Organization-scoped project model.

    Each project belongs to an organization and tracks a specific development
    project with its working directory, optional worktree, and associated collections.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='projects',
        help_text="The organization that owns this project"
    )

    # Required fields
    name = models.CharField(
        max_length=255,
        help_text="Project name"
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
        help_text="Auto-generated canonical email address (e.g., project-slug.org-slug@zoea.studio)"
    )
    email_alias = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="User-configurable email alias (e.g., 'bob' -> bob.org-slug@zoea.studio)"
    )
    working_directory = models.CharField(
        max_length=500,
        help_text="Path to the project's working directory"
    )

    # Optional fields
    worktree_directory = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Path to the project's worktree directory (if using git worktrees)"
    )
    description = models.TextField(
        blank=True,
        help_text="Project description"
    )

    # Visual customization
    color_theme = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        blank=True,
        null=True,
        help_text="Color theme for the project UI"
    )
    avatar = models.ImageField(
        upload_to='projects/avatars/',
        blank=True,
        null=True,
        help_text="Project avatar image"
    )
    use_primary_header = models.BooleanField(
        default=False,
        help_text="Use theme primary color for app header background"
    )

    # LLM Configuration (nullable = inherit from app defaults)
    llm_provider = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="LLM provider name (openai, gemini, ollama). Inherits from app defaults if not set."
    )
    llm_model_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Model ID to use (e.g., gpt-4o, gemini-2.5-flash). Inherits from app defaults if not set."
    )
    openai_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Project-specific OpenAI API key. Uses app default if not set."
    )
    gemini_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Project-specific Gemini API key. Uses app default if not set."
    )
    local_model_endpoint = models.URLField(
        blank=True,
        null=True,
        help_text="Endpoint URL for local models (Ollama, LM Studio)"
    )

    # Gemini File Search integration
    gemini_store_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text="Gemini File Search store ID for this project"
    )
    gemini_store_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Display name of the Gemini File Search store"
    )
    gemini_synced_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time documents were synced to Gemini File Search"
    )

    # Relationships
    # project_collections will be added via reverse relationship from Collection model

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_projects',
        help_text="User who created this project"
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ['-created_at']
        unique_together = [
            ['organization', 'name'],
            ['organization', 'slug'],
            ['organization', 'email_alias'],
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

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
            # Check for conflict with project slugs in the same org
            if Project.objects.filter(
                organization=self.organization,
                slug=self.email_alias
            ).exclude(pk=self.pk).exists():
                raise ValidationError({
                    'email_alias': f'Email alias "{self.email_alias}" conflicts with an existing project slug.'
                })
            # Check for conflict with workspace aliases in the same org (cross-model uniqueness)
            # Note: This check is only valid after Workspace has email_alias field
            from workspaces.models import Workspace
            if hasattr(Workspace, 'email_alias'):
                if Workspace.objects.filter(
                    project__organization=self.organization,
                    email_alias=self.email_alias
                ).exists():
                    raise ValidationError({
                        'email_alias': f'Email alias "{self.email_alias}" is already used by a workspace.'
                    })

    def save(self, *args, **kwargs):
        """Auto-generate slug and canonical_email from name if not set."""
        if not self.slug:
            base_slug = slugify_for_email(self.name)
            slug = base_slug
            counter = 1
            # Handle duplicates within the organization
            while Project.objects.filter(
                organization=self.organization,
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        # Always regenerate canonical_email from slug (in case slug or org changed)
        self.canonical_email = generate_project_canonical_email(
            self.slug, self.organization.slug
        )
        super().save(*args, **kwargs)

    @property
    def theme_color(self):
        """Return the hex color for this project's theme."""
        if self.color_theme:
            return THEME_COLORS.get(self.color_theme, THEME_COLORS['claude'])
        return THEME_COLORS['claude']  # Default fallback

    @property
    def avatar_url(self):
        """Return the URL for this project's avatar, or None if not set."""
        if self.avatar:
            return self.avatar.url
        return None

    @property
    def alias_email(self):
        """Return the full alias email address, or None if no alias set."""
        if not self.email_alias:
            return None
        return generate_alias_email(self.email_alias, self.organization.slug)
