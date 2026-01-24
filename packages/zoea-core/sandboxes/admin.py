"""Django admin configuration for sandboxes models."""

from django.contrib import admin

from .models import SandboxConfig, SandboxSession


@admin.register(SandboxConfig)
class SandboxConfigAdmin(admin.ModelAdmin):
    """Admin interface for SandboxConfig."""

    list_display = [
        "name",
        "sandbox_type",
        "organization",
        "is_default",
        "docker_image",
        "created_at",
    ]
    list_filter = ["sandbox_type", "is_default", "organization"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["organization", "created_by"]

    fieldsets = [
        (None, {"fields": ["name", "description", "organization"]}),
        ("Type", {"fields": ["sandbox_type", "is_default"]}),
        (
            "Docker Settings",
            {
                "fields": ["docker_image"],
                "classes": ["collapse"],
            },
        ),
        (
            "Resources",
            {
                "fields": ["resource_limits", "allowed_paths", "workspace_base_path"],
            },
        ),
        (
            "Environment",
            {
                "fields": ["environment_variables", "shell_command"],
            },
        ),
        (
            "Security",
            {
                "fields": ["network_enabled", "mount_project_readonly"],
            },
        ),
        ("Metadata", {"fields": ["created_by", "created_at", "updated_at"]}),
    ]


@admin.register(SandboxSession)
class SandboxSessionAdmin(admin.ModelAdmin):
    """Admin interface for SandboxSession."""

    list_display = [
        "session_id_short",
        "name",
        "status",
        "config",
        "organization",
        "execution_count",
        "created_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["name", "session_id", "container_id", "tmux_session_name"]
    readonly_fields = [
        "session_id",
        "created_at",
        "started_at",
        "terminated_at",
        "execution_count",
        "last_activity_at",
    ]
    raw_id_fields = ["organization", "project", "config", "execution_run", "created_by"]

    def session_id_short(self, obj):
        """Show truncated session ID."""
        return str(obj.session_id)[:8]

    session_id_short.short_description = "Session ID"

    fieldsets = [
        (None, {"fields": ["session_id", "name", "organization", "project"]}),
        ("Configuration", {"fields": ["config", "runtime_config"]}),
        ("Status", {"fields": ["status", "status_message"]}),
        (
            "Runtime",
            {
                "fields": [
                    "container_id",
                    "tmux_session_name",
                    "vm_instance_id",
                    "workspace_path",
                ]
            },
        ),
        (
            "Activity",
            {
                "fields": ["execution_count", "last_activity_at"],
            },
        ),
        (
            "Timing",
            {
                "fields": ["created_at", "started_at", "terminated_at"],
            },
        ),
        ("Execution", {"fields": ["execution_run"]}),
        ("Metadata", {"fields": ["created_by"]}),
    ]
