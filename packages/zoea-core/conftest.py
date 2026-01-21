"""
Pytest configuration for Django tests with SQLite.

Uses SQLite in-memory database for fast testing - no Docker required.
"""

import os

# Set test settings module before importing Django
os.environ["DJANGO_SETTINGS_MODULE"] = "zoea.settings_test"
