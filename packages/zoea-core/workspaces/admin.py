"""
Django admin configuration for workspaces.
"""

from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(MPTTModelAdmin):
    """
    Admin interface for Workspace model with MPTT tree display.
    """

    list_display = ['name', 'project', 'parent', 'created_by', 'created_at']
    list_filter = ['project__organization', 'created_at']
    search_fields = ['name', 'description', 'project__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['project', 'parent', 'created_by']

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'project', 'parent']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('project', 'project__organization', 'parent', 'created_by')
