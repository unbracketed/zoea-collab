"""Django app configuration for agent_wrappers."""

from django.apps import AppConfig


class AgentWrappersConfig(AppConfig):
    """Configuration for the agent_wrappers app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "agent_wrappers"
    verbose_name = "External Agent Wrappers"
