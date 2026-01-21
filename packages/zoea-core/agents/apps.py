from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agents"
    verbose_name = "Agent Orchestration"

    def ready(self):
        # Import registry to trigger tool auto-discovery
        from agents.registry import ToolRegistry

        ToolRegistry.get_instance()
