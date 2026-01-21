"""
Django admin configuration for Agent models.
"""

from django.contrib import admin

from .models import ProjectToolConfig, ToolExecutionLog


@admin.register(ProjectToolConfig)
class ProjectToolConfigAdmin(admin.ModelAdmin):
    """Admin for ProjectToolConfig model."""

    list_display = [
        "tool_name",
        "project",
        "is_enabled",
        "organization",
        "created_at",
        "created_by",
    ]
    list_filter = [
        "is_enabled",
        "tool_name",
        "organization",
    ]
    search_fields = [
        "tool_name",
        "project__name",
        "organization__name",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    raw_id_fields = [
        "organization",
        "project",
        "created_by",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "organization",
                    "project",
                    "tool_name",
                ]
            },
        ),
        (
            "Configuration",
            {
                "fields": [
                    "is_enabled",
                    "config_overrides",
                ]
            },
        ),
        (
            "Metadata",
            {
                "fields": [
                    "created_by",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(ToolExecutionLog)
class ToolExecutionLogAdmin(admin.ModelAdmin):
    """Admin for ToolExecutionLog model."""

    list_display = [
        "tool_name",
        "agent_name",
        "success",
        "duration_ms",
        "executed_at",
        "user",
        "project",
    ]
    list_filter = [
        "success",
        "tool_name",
        "organization",
        "executed_at",
    ]
    search_fields = [
        "tool_name",
        "agent_name",
        "user__username",
        "project__name",
    ]
    readonly_fields = [
        "organization",
        "project",
        "workspace",
        "user",
        "tool_name",
        "agent_name",
        "input_summary",
        "output_summary",
        "duration_ms",
        "success",
        "error_message",
        "executed_at",
    ]
    raw_id_fields = [
        "organization",
        "project",
        "workspace",
        "user",
    ]
    date_hierarchy = "executed_at"

    def has_add_permission(self, request):
        """Execution logs are created programmatically only."""
        return False

    def has_change_permission(self, request, obj=None):
        """Execution logs are immutable."""
        return False
