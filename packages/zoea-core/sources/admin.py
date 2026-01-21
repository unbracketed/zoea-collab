"""
Django admin interface for sources.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import Source


class SourceForm(forms.ModelForm):
    """Custom form for Source admin that auto-populates organization."""

    class Meta:
        model = Source
        fields = '__all__'
        help_texts = {
            'config': (
                'JSON configuration for the source. '
                '<br><strong>Local filesystem example:</strong> '
                '<code>{"path": "/absolute/path/to/documents", "pattern": "**/*.{md,pdf,png}"}</code>'
                '<br><strong>S3 example:</strong> '
                '<code>{"bucket": "my-bucket", "prefix": "docs/", "region": "us-west-2"}</code>'
            )
        }

    def clean(self):
        """Set organization from project before validation."""
        cleaned_data = super().clean()
        project = cleaned_data.get('project')

        # Auto-populate organization from project
        if project and not cleaned_data.get('organization'):
            cleaned_data['organization'] = project.organization
            self.instance.organization = project.organization

        return cleaned_data


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    """
    Admin interface for Source model.

    Features:
    - Organization-scoped filtering
    - Test connection action
    - Display connection status
    - JSON field editing with syntax highlighting
    """

    form = SourceForm

    list_display = [
        'name',
        'source_type',
        'project',
        'organization',
        'is_active',
        'connection_status',
        'last_sync_at',
        'created_at',
    ]

    list_filter = [
        'source_type',
        'is_active',
        'organization',
        'created_at',
    ]

    search_fields = [
        'name',
        'description',
        'project__name',
        'organization__name',
    ]

    readonly_fields = [
        'organization',
        'created_at',
        'updated_at',
        'created_by',
        'last_sync_at',
        'last_test_at',
        'last_test_success',
        'display_name',
    ]

    fieldsets = [
        ('Basic Information', {
            'fields': [
                'project',
                'organization',
                'name',
                'description',
                'source_type',
            ]
        }),
        ('Configuration', {
            'fields': [
                'config',
                'display_name',
            ]
        }),
        ('Status', {
            'fields': [
                'is_active',
                'last_sync_at',
                'last_test_at',
                'last_test_success',
            ]
        }),
        ('Metadata', {
            'fields': [
                'created_at',
                'updated_at',
                'created_by',
            ],
            'classes': ['collapse']
        }),
    ]

    actions = ['test_connection', 'activate_sources', 'deactivate_sources']

    def connection_status(self, obj):
        """Display connection test status with color coding."""
        if obj.last_test_success is None:
            return format_html(
                '<span style="color: {};">●</span> {}',
                'gray',
                'Not tested'
            )
        elif obj.last_test_success:
            return format_html(
                '<span style="color: {};">●</span> {}',
                'green',
                'Connected'
            )
        else:
            return format_html(
                '<span style="color: {};">●</span> {}',
                'red',
                'Failed'
            )

    connection_status.short_description = 'Connection'

    def display_name(self, obj):
        """Display the source's full display name."""
        return obj.get_display_name()

    display_name.short_description = 'Display Name'

    def test_connection(self, request, queryset):
        """Test connection for selected sources."""
        success_count = 0
        fail_count = 0

        for source in queryset:
            if source.test_connection():
                success_count += 1
            else:
                fail_count += 1

        self.message_user(
            request,
            f"Tested {queryset.count()} source(s): "
            f"{success_count} successful, {fail_count} failed"
        )

    test_connection.short_description = "Test connection for selected sources"

    def activate_sources(self, request, queryset):
        """Activate selected sources."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} source(s)")

    activate_sources.short_description = "Activate selected sources"

    def deactivate_sources(self, request, queryset):
        """Deactivate selected sources."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} source(s)")

    deactivate_sources.short_description = "Deactivate selected sources"

    def save_model(self, request, obj, form, change):
        """Set created_by on new sources."""
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Filter queryset by user's organizations."""
        qs = super().get_queryset(request)

        # Superusers can see all sources
        if request.user.is_superuser:
            return qs

        # Regular users only see sources from their organizations
        return qs.for_user(request.user)
