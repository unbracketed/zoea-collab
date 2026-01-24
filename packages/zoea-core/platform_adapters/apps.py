"""Django app configuration for platform_adapters."""

from django.apps import AppConfig


class PlatformAdaptersConfig(AppConfig):
    """Configuration for the platform_adapters app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "platform_adapters"
    verbose_name = "Platform Adapters"

    def ready(self):
        """Import signal handlers when the app is ready."""
        pass
