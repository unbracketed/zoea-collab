"""App configuration for the context_clipboards Django app."""

from django.apps import AppConfig


class ContextClipboardsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "context_clipboards"
    verbose_name = "Context Clipboards"

    def ready(self):
        # Import signal handlers when the app is ready.
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Signals are optional during early scaffolding; swallow errors until implemented.
            pass
