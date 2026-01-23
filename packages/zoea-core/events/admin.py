from django.contrib import admin

from .models import EventTrigger


@admin.register(EventTrigger)
class EventTriggerAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "event_type",
        "project",
        "organization",
        "is_enabled",
        "skill_count",
        "created_at",
    ]
    list_filter = ["event_type", "is_enabled", "organization"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["organization", "project", "created_by"]

