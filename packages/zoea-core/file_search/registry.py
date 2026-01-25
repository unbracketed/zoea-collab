"""
Registry for File Search Store backend implementations.

Provides a central registry for registering and retrieving file search
backend implementations, with support for a configurable default backend.
"""

from django.conf import settings

from .base import FileSearchStore
from .exceptions import BackendNotFoundError, ConfigurationError


class FileSearchRegistry:
    """
    Registry for file search backend implementations.

    Usage:
        # Register a backend
        FileSearchRegistry.register('gemini', GeminiFileSearchStore)

        # Get the default backend
        store = FileSearchRegistry.get()

        # Get a specific backend
        store = FileSearchRegistry.get('chromadb')

        # List available backends
        backends = FileSearchRegistry.list_backends()
    """

    _backends: dict[str, type[FileSearchStore]] = {}
    _instances: dict[str, FileSearchStore] = {}
    _default: str | None = None
    _ensure_backends: callable = None  # Set by file_search/__init__.py
    _backends_loaded: bool = False

    @classmethod
    def _load_backends(cls) -> None:
        """Ensure backends are loaded (lazy initialization)."""
        if not cls._backends_loaded and cls._ensure_backends is not None:
            cls._backends_loaded = True
            cls._ensure_backends()

    @classmethod
    def register(
        cls,
        name: str,
        backend_class: type[FileSearchStore],
        *,
        set_default: bool = False,
    ) -> None:
        """
        Register a backend implementation.

        Args:
            name: Unique identifier for the backend
            backend_class: FileSearchStore subclass
            set_default: If True, set this as the default backend
        """
        if not issubclass(backend_class, FileSearchStore):
            raise ConfigurationError(
                f"Backend class must be a subclass of FileSearchStore, got {backend_class.__name__}"
            )

        cls._backends[name] = backend_class

        if set_default or cls._default is None:
            cls._default = name

    @classmethod
    def unregister(cls, name: str) -> None:
        """
        Unregister a backend.

        Args:
            name: Backend identifier to remove
        """
        cls._backends.pop(name, None)
        cls._instances.pop(name, None)

        if cls._default == name:
            cls._default = next(iter(cls._backends), None)

    @classmethod
    def get(cls, name: str | None = None) -> FileSearchStore:
        """
        Get a backend instance by name or the default.

        Args:
            name: Backend identifier, or None for default

        Returns:
            FileSearchStore instance

        Raises:
            BackendNotFoundError: If backend not registered
            ConfigurationError: If no default is configured
        """
        # Ensure backends are loaded
        cls._load_backends()

        # Determine which backend to use
        backend_name = name

        if backend_name is None:
            # Try Django settings first
            backend_name = getattr(settings, "FILE_SEARCH_BACKEND", None)

        if backend_name is None:
            backend_name = cls._default

        if backend_name is None:
            raise ConfigurationError(
                "No file search backend configured. "
                "Set FILE_SEARCH_BACKEND in settings or register a default backend."
            )

        if backend_name not in cls._backends:
            available = ", ".join(cls._backends.keys()) or "none"
            raise BackendNotFoundError(
                f"Backend '{backend_name}' not found. Available: {available}"
            )

        # Return cached instance or create new one
        if backend_name not in cls._instances:
            cls._instances[backend_name] = cls._backends[backend_name]()

        return cls._instances[backend_name]

    @classmethod
    def set_default(cls, name: str) -> None:
        """
        Set the default backend.

        Args:
            name: Backend identifier

        Raises:
            BackendNotFoundError: If backend not registered
        """
        if name not in cls._backends:
            raise BackendNotFoundError(f"Backend '{name}' not registered")

        cls._default = name

    @classmethod
    def list_backends(cls) -> list[str]:
        """
        List all registered backend names.

        Returns:
            List of backend identifiers
        """
        cls._load_backends()
        return list(cls._backends.keys())

    @classmethod
    def get_default(cls) -> str | None:
        """
        Get the current default backend name.

        Returns:
            Default backend name or None
        """
        cls._load_backends()
        return getattr(settings, "FILE_SEARCH_BACKEND", None) or cls._default

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered backends and instances.

        Primarily for testing purposes.
        """
        cls._backends.clear()
        cls._instances.clear()
        cls._default = None
