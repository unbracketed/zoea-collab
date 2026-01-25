"""
Django app configuration for file_search.
"""

from django.apps import AppConfig


class FileSearchConfig(AppConfig):
    name = "file_search"
    verbose_name = "File Search"
    default_auto_field = "django.db.models.BigAutoField"
