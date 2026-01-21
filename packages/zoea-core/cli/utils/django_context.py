"""Django context management for CLI commands."""

import os
import sys
from functools import wraps
from pathlib import Path

import django
from django.apps import apps


class DjangoContextManager:
    """Manages Django setup for CLI commands."""

    _initialized = False

    @staticmethod
    def setup():
        """Initialize Django environment."""
        if DjangoContextManager._initialized:
            return

        # Add the backend directory to Python path if not already there
        # This ensures Django apps can be imported correctly
        backend_dir = Path(__file__).resolve().parent.parent.parent
        backend_dir_str = str(backend_dir)
        if backend_dir_str not in sys.path:
            sys.path.insert(0, backend_dir_str)

        # Set Django settings module
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zoea.settings")

        # Only call setup if not already configured
        if not apps.ready:
            django.setup()

        DjangoContextManager._initialized = True

    @staticmethod
    def with_django(func):
        """Decorator to ensure Django is set up before running a command."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            DjangoContextManager.setup()
            return func(*args, **kwargs)

        return wrapper


def with_django(func):
    """Convenience decorator for ensuring Django context."""
    return DjangoContextManager.with_django(func)
