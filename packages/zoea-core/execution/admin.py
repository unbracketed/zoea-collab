from django.contrib import admin

from .models import ExecutionRun


@admin.register(ExecutionRun)
class ExecutionRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "run_id",
        "status",
        "trigger_type",
        "workflow_slug",
        "organization",
        "created_at",
    )
    list_filter = ("status", "trigger_type", "workflow_slug", "created_at")
    search_fields = ("run_id", "workflow_slug", "source_type")
