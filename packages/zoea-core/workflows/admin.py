from django.contrib import admin
from .models import Workflow


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    """
    Admin interface for Workflow management.

    Displays organization-scoped workflows with their metadata.
    """
    list_display = [
        'name',
        'organization',
        'created_by',
        'created_at',
        'updated_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'created_by']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Configuration', {
            'fields': ['metadata']
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
