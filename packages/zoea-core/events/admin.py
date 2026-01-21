from django.contrib import admin

from .models import EventTrigger, EventTriggerRun


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


@admin.register(EventTriggerRun)
class EventTriggerRunAdmin(admin.ModelAdmin):
    list_display = [
        "run_id",
        "trigger",
        "source_type",
        "source_id",
        "status",
        "duration_seconds",
        "created_at",
    ]
    list_filter = ["status", "source_type", "organization"]
    search_fields = ["run_id", "trigger__name"]
    readonly_fields = [
        "run_id",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
    ]
    raw_id_fields = ["organization", "trigger", "artifacts"]
