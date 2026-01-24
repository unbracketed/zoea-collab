"""Django admin configuration for output_dispatch models."""

from django.contrib import admin

from .models import DispatchLog, OutputRoute


@admin.register(OutputRoute)
class OutputRouteAdmin(admin.ModelAdmin):
    """Admin interface for OutputRoute."""

    list_display = [
        "name",
        "destination_type",
        "organization",
        "trigger",
        "project",
        "is_enabled",
        "priority",
        "created_at",
    ]
    list_filter = ["destination_type", "is_enabled", "organization"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = [
        "organization",
        "trigger",
        "project",
        "platform_connection",
        "document_folder",
        "created_by",
    ]

    fieldsets = [
        (None, {"fields": ["name", "description", "organization"]}),
        ("Destination", {"fields": ["destination_type", "is_enabled", "priority"]}),
        (
            "Scope",
            {
                "fields": ["trigger", "project"],
                "description": "Leave blank for organization-wide route",
            },
        ),
        (
            "Platform Config",
            {
                "fields": ["platform_connection", "channel_id"],
            },
        ),
        (
            "Webhook Config",
            {
                "fields": ["webhook_url"],
                "classes": ["collapse"],
            },
        ),
        (
            "Document Config",
            {
                "fields": ["document_folder", "document_name_template"],
                "classes": ["collapse"],
            },
        ),
        (
            "Formatting",
            {
                "fields": ["template", "include_artifacts", "format_type"],
            },
        ),
        (
            "Filtering",
            {
                "fields": ["output_filter"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_by", "created_at", "updated_at"]}),
    ]


@admin.register(DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    """Admin interface for DispatchLog."""

    list_display = [
        "dispatch_id_short",
        "route",
        "destination_type",
        "status",
        "duration",
        "created_at",
    ]
    list_filter = ["status", "destination_type", "organization"]
    search_fields = ["dispatch_id", "status_message"]
    readonly_fields = [
        "dispatch_id",
        "created_at",
        "sent_at",
        "completed_at",
        "retry_count",
    ]
    raw_id_fields = ["organization", "route", "execution_run", "agent_run"]

    def dispatch_id_short(self, obj):
        """Show truncated dispatch ID."""
        return str(obj.dispatch_id)[:8]

    dispatch_id_short.short_description = "Dispatch ID"

    def duration(self, obj):
        """Show duration."""
        if obj.duration_ms:
            return f"{obj.duration_ms}ms"
        return "-"

    duration.short_description = "Duration"

    fieldsets = [
        (None, {"fields": ["dispatch_id", "organization", "route"]}),
        ("Source", {"fields": ["execution_run", "agent_run"]}),
        ("Destination", {"fields": ["destination_type", "destination_info"]}),
        ("Status", {"fields": ["status", "status_message", "retry_count"]}),
        (
            "Payload",
            {
                "fields": ["payload", "response_data"],
                "classes": ["collapse"],
            },
        ),
        (
            "Timing",
            {
                "fields": ["created_at", "sent_at", "completed_at"],
            },
        ),
    ]
