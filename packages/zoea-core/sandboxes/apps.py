"""Django app configuration for sandboxes."""

from django.apps import AppConfig


class SandboxesConfig(AppConfig):
    """Configuration for the sandboxes app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "sandboxes"
    verbose_name = "Agent Sandboxes"
