from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Admin interface for Project management.

    Displays organization-scoped projects with their working directories
    and associated metadata.
    """
    list_display = [
        'name',
        'organization',
        'color_theme',
        'working_directory',
        'created_by',
        'created_at'
    ]
    list_filter = ['organization', 'color_theme', 'created_at']
    search_fields = ['name', 'description', 'working_directory', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'created_by']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Appearance', {
            'fields': ['color_theme', 'avatar']
        }),
        ('Directories', {
            'fields': ['working_directory', 'worktree_directory']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('organization', 'created_by')
