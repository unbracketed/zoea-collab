"""
Service and workflow registries for discovery and instantiation.

Provides singleton registries for:
- Services: External integrations (GitHub, AI, Documents)
- Workflows: Discovered workflow definitions
"""

import importlib.util
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

from .exceptions import ServiceNotFoundError

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Registry for workflow services.

    Services can be registered by name and instantiated with config.
    Built-in services are auto-discovered from workflows.services module.

    Example:
        registry = ServiceRegistry.get_instance()
        service = registry.create('PyGithubInterface', {'repo': 'user/repo'})
    """

    _instance: Optional["ServiceRegistry"] = None

    def __init__(self):
        self._services: Dict[str, Type] = {}
        self._factories: Dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> "ServiceRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_builtins()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def _register_builtins(self) -> None:
        """Register built-in services."""
        try:
            from .services.ai import AIService
            from .services.documents import DocumentService
            from .services.github import PyGithubInterface

            self.register("PyGithubInterface", PyGithubInterface)
            self.register("DocumentService", DocumentService)
            self.register("AIService", AIService)
            self.register("ChatAgentService", AIService)  # Alias
            logger.debug("Registered built-in services")
        except ImportError as e:
            logger.warning(f"Could not register built-in services: {e}")

    def register(self, name: str, service_class: Type) -> None:
        """
        Register a service class by name.

        Args:
            name: Service name for lookup
            service_class: The service class to register
        """
        self._services[name] = service_class
        logger.debug(f"Registered service: {name}")

    def register_factory(self, name: str, factory: Callable[..., Any]) -> None:
        """
        Register a factory function for custom instantiation.

        Args:
            name: Service name for lookup
            factory: Callable that returns a service instance
        """
        self._factories[name] = factory

    def create(self, name: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create a service instance by name.

        Args:
            name: Registered service name
            config: Optional configuration dict passed to constructor

        Returns:
            Service instance

        Raises:
            ServiceNotFoundError: If service not registered
        """
        config = config or {}

        # Try factory first
        if name in self._factories:
            return self._factories[name](**config)

        # Then registered class
        if name not in self._services:
            raise ServiceNotFoundError(f"Service not found: {name}")

        service_class = self._services[name]
        return service_class(**config) if config else service_class()

    def get_service_class(self, name: str) -> Optional[Type]:
        """Get service class without instantiation."""
        return self._services.get(name)

    def list_services(self) -> list[str]:
        """List all registered service names."""
        return list(self._services.keys())


class WorkflowRegistry:
    """
    Registry for discovered workflow definitions.

    Tracks available workflows by slug, with references to their
    config files and flow builder functions.

    Example:
        registry = WorkflowRegistry.get_instance()
        registry.register('plan-github-issue', config_path, build_flow)
        workflow = registry.get('plan-github-issue')
    """

    _instance: Optional["WorkflowRegistry"] = None

    def __init__(self):
        self._workflows: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "WorkflowRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def register(
        self,
        slug: str,
        config_path: Path,
        flow_builder: Optional[Callable] = None,
    ) -> None:
        """
        Register a workflow by slug.

        Args:
            slug: Workflow identifier
            config_path: Path to flow-config.yaml
            flow_builder: Optional callable that returns a Flow instance
        """
        self._workflows[slug] = {
            "config_path": config_path,
            "flow_builder": flow_builder,
        }
        logger.debug(f"Registered workflow: {slug}")

    def get(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get workflow definition by slug."""
        return self._workflows.get(slug)

    def list_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered workflows."""
        return self._workflows.copy()

    def discover_builtins(self, workflows_path: Path) -> None:
        """
        Discover and register built-in workflows.

        Args:
            workflows_path: Path to the workflows/ directory
        """
        builtin_dir = workflows_path / "builtin"
        if not builtin_dir.exists():
            return

        for workflow_dir in builtin_dir.iterdir():
            if not workflow_dir.is_dir():
                continue

            config_path = workflow_dir / "flow-config.yaml"
            if not config_path.exists():
                continue

            # Try to import flow builder
            flow_builder = None
            flow_module_path = workflow_dir / "flow.py"
            if flow_module_path.exists():
                try:
                    flow_builder = _import_flow_builder(flow_module_path)
                except Exception as e:
                    logger.warning(f"Could not import flow builder for {workflow_dir.name}: {e}")

            self.register(workflow_dir.name, config_path, flow_builder)


def _import_flow_builder(flow_module_path: Path) -> Callable:
    """
    Dynamically import a build_flow function from a workflow module.

    Args:
        flow_module_path: Path to flow.py file

    Returns:
        The build_flow callable

    Raises:
        ImportError: If module can't be loaded or build_flow not found
    """
    spec = importlib.util.spec_from_file_location("flow", flow_module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec from {flow_module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "build_flow"):
        raise ImportError(f"Module {flow_module_path} has no build_flow function")

    return module.build_flow
