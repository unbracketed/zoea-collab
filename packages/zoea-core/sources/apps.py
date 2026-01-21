"""
Django app configuration for sources.
"""

from django.apps import AppConfig


class SourcesConfig(AppConfig):
    """Configuration for the sources app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sources'
    verbose_name = 'Document Sources'

    def ready(self):
        """
        Initialize the sources app.

        This method is called when Django starts. It ensures all source
        implementations are imported and registered.
        """
        # Import source implementations to register them
        from . import local  # noqa: F401
