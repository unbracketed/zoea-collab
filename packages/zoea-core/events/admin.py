from django.contrib import admin

from .models import EventTrigger, ScheduledEvent


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


@admin.register(ScheduledEvent)
class ScheduledEventAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "schedule_type",
        "trigger",
        "organization",
        "is_enabled",
        "next_run_at",
        "last_run_at",
        "run_count",
    ]
    list_filter = ["schedule_type", "is_enabled", "organization"]
    search_fields = ["name", "description", "cron_expression"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "last_run_at",
        "run_count",
        "next_run_at",
        "django_q_schedule_id",
    ]
    raw_id_fields = ["organization", "trigger", "created_by"]

    fieldsets = [
        (None, {"fields": ["name", "description", "organization", "trigger"]}),
        (
            "Schedule Configuration",
            {
                "fields": [
                    "schedule_type",
                    "scheduled_at",
                    "cron_expression",
                    "timezone_name",
                ]
            },
        ),
        ("Event Data", {"fields": ["event_data"]}),
        (
            "Status",
            {
                "fields": [
                    "is_enabled",
                    "next_run_at",
                    "last_run_at",
                    "run_count",
                    "django_q_schedule_id",
                ]
            },
        ),
        ("Metadata", {"fields": ["created_at", "updated_at", "created_by"]}),
    ]

