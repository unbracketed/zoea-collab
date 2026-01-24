"""Django admin configuration for agent_wrappers models."""

from django.contrib import admin

from .models import ExternalAgentConfig, ExternalAgentRun


@admin.register(ExternalAgentConfig)
class ExternalAgentConfigAdmin(admin.ModelAdmin):
    """Admin interface for ExternalAgentConfig."""

    list_display = [
        "name",
        "agent_type",
        "organization",
        "is_enabled",
        "is_default",
        "max_steps",
        "timeout_seconds",
        "created_at",
    ]
    list_filter = ["agent_type", "is_enabled", "is_default", "organization"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["organization", "default_sandbox", "created_by"]

    fieldsets = [
        (None, {"fields": ["name", "description", "organization"]}),
        ("Agent Type", {"fields": ["agent_type", "is_enabled", "is_default"]}),
        (
            "Credentials & Settings",
            {
                "fields": ["credentials", "settings"],
                "classes": ["collapse"],
            },
        ),
        (
            "Execution",
            {
                "fields": [
                    "default_sandbox",
                    "max_steps",
                    "timeout_seconds",
                ]
            },
        ),
        (
            "CLI Configuration",
            {
                "fields": ["cli_command", "cli_args"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_by", "created_at", "updated_at"]}),
    ]


@admin.register(ExternalAgentRun)
class ExternalAgentRunAdmin(admin.ModelAdmin):
    """Admin interface for ExternalAgentRun."""

    list_display = [
        "run_id_short",
        "config",
        "status",
        "organization",
        "steps_taken",
        "duration",
        "created_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["run_id", "prompt", "response"]
    readonly_fields = [
        "run_id",
        "created_at",
        "started_at",
        "completed_at",
        "steps_taken",
        "tokens_used",
    ]
    raw_id_fields = [
        "organization",
        "project",
        "config",
        "sandbox_session",
        "execution_run",
        "created_by",
    ]

    def run_id_short(self, obj):
        """Show truncated run ID."""
        return str(obj.run_id)[:8]

    run_id_short.short_description = "Run ID"

    def duration(self, obj):
        """Show duration."""
        if obj.duration_seconds:
            return f"{obj.duration_seconds:.1f}s"
        return "-"

    duration.short_description = "Duration"

    fieldsets = [
        (None, {"fields": ["run_id", "organization", "project"]}),
        ("Configuration", {"fields": ["config", "sandbox_session", "execution_run"]}),
        ("Status", {"fields": ["status", "status_message"]}),
        (
            "Input",
            {
                "fields": ["prompt", "system_prompt", "context_files"],
            },
        ),
        (
            "Output",
            {
                "fields": ["response", "output_stream", "artifacts"],
                "classes": ["collapse"],
            },
        ),
        (
            "Usage",
            {
                "fields": ["tokens_used", "steps_taken"],
            },
        ),
        (
            "Timing",
            {
                "fields": ["created_at", "started_at", "completed_at"],
            },
        ),
        (
            "Runtime Config",
            {
                "fields": ["runtime_config"],
                "classes": ["collapse"],
            },
        ),
        ("Metadata", {"fields": ["created_by"]}),
    ]
