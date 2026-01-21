"""
Test settings for Django tests with SQLite.

This settings file configures Django to use SQLite for database testing.
Import all settings from the main settings file, then override the database.
"""

import os

# Prevent DATABASE_URL from being used
if "DATABASE_URL" in os.environ:
    del os.environ["DATABASE_URL"]

from zoea.settings import *  # noqa: F401, F403

# Override database to use SQLite for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            "NAME": ":memory:",
        },
    }
}
