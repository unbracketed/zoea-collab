"""Django admin configuration for platform_adapters models."""

from django.contrib import admin

from .models import PlatformMessage, PlatformConnection


@admin.register(PlatformConnection)
class PlatformConnectionAdmin(admin.ModelAdmin):
    """Admin interface for PlatformConnection."""

    list_display = [
        "name",
        "platform_type",
        "organization",
        "project",
        "status",
        "message_count",
        "last_message_at",
        "created_at",
    ]
    list_filter = ["platform_type", "status", "organization"]
    search_fields = ["name", "description", "connection_id"]
    readonly_fields = ["connection_id", "webhook_secret", "message_count", "last_message_at"]
    ordering = ["-created_at"]

    fieldsets = [
        (None, {"fields": ["name", "description", "organization", "project"]}),
        ("Platform", {"fields": ["platform_type", "status", "status_message"]}),
        (
            "Webhook",
            {
                "fields": ["connection_id", "webhook_secret"],
                "description": "Webhook URL and secret for receiving messages",
            },
        ),
        (
            "Configuration",
            {
                "fields": ["config", "credentials"],
                "classes": ["collapse"],
            },
        ),
        (
            "Statistics",
            {
                "fields": ["message_count", "last_message_at"],
            },
        ),
    ]


@admin.register(PlatformMessage)
class PlatformMessageAdmin(admin.ModelAdmin):
    """Admin interface for PlatformMessage."""

    list_display = [
        "message_id",
        "connection",
        "direction",
        "status",
        "sender_name",
        "content_preview",
        "received_at",
    ]
    list_filter = ["status", "direction", "connection__platform_type"]
    search_fields = ["content", "sender_name", "sender_email", "external_id"]
    readonly_fields = ["message_id", "received_at", "processed_at"]
    ordering = ["-received_at"]

    def content_preview(self, obj):
        """Show truncated content."""
        if len(obj.content) > 50:
            return obj.content[:50] + "..."
        return obj.content

    content_preview.short_description = "Content"

    fieldsets = [
        (None, {"fields": ["message_id", "connection", "organization", "project"]}),
        ("Status", {"fields": ["direction", "status", "status_message"]}),
        (
            "Sender",
            {"fields": ["sender_id", "sender_name", "sender_email"]},
        ),
        (
            "Message",
            {"fields": ["content", "content_type", "attachments"]},
        ),
        (
            "Platform",
            {"fields": ["external_id", "channel_id", "thread_id", "metadata"]},
        ),
        (
            "Timestamps",
            {"fields": ["received_at", "processed_at", "platform_timestamp"]},
        ),
        (
            "Raw Data",
            {
                "fields": ["raw_payload"],
                "classes": ["collapse"],
            },
        ),
    ]
