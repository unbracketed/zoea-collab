"""
Registry for document source implementations.

This module provides a registry pattern for registering and retrieving
document source classes by their type identifier.
"""

from typing import Dict, Type
from .base import SourceInterface


class SourceRegistry:
    """
    Registry for document source implementations.

    This class maintains a mapping of source type identifiers to their
    implementation classes. Use this to register new source types and
    retrieve them by name.

    Example:
        # Register a source type
        SourceRegistry.register('s3', S3Source)

        # Retrieve a source class
        source_class = SourceRegistry.get('s3')
        source = source_class({'bucket': 'my-bucket'})
    """

    _registry: Dict[str, Type[SourceInterface]] = {}

    @classmethod
    def register(cls, source_type: str, source_class: Type[SourceInterface]) -> None:
        """
        Register a source implementation.

        Args:
            source_type: Type identifier (e.g., 'local', 's3', 'r2').
            source_class: Source implementation class.

        Raises:
            ValueError: If source_type is already registered.
        """
        if source_type in cls._registry:
            raise ValueError(
                f"Source type '{source_type}' is already registered "
                f"with class {cls._registry[source_type].__name__}"
            )

        if not issubclass(source_class, SourceInterface):
            raise ValueError(
                f"Source class {source_class.__name__} must inherit from SourceInterface"
            )

        cls._registry[source_type] = source_class

    @classmethod
    def get(cls, source_type: str) -> Type[SourceInterface]:
        """
        Get a registered source implementation.

        Args:
            source_type: Type identifier (e.g., 'local', 's3', 'r2').

        Returns:
            Source implementation class.

        Raises:
            ValueError: If source_type is not registered.
        """
        if source_type not in cls._registry:
            available = ', '.join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unknown source type '{source_type}'. "
                f"Available types: {available or 'none'}"
            )

        return cls._registry[source_type]

    @classmethod
    def get_registered_types(cls) -> Dict[str, Type[SourceInterface]]:
        """
        Get all registered source types.

        Returns:
            Dictionary mapping type identifiers to source classes.
        """
        return cls._registry.copy()

    @classmethod
    def is_registered(cls, source_type: str) -> bool:
        """
        Check if a source type is registered.

        Args:
            source_type: Type identifier to check.

        Returns:
            True if registered, False otherwise.
        """
        return source_type in cls._registry

    @classmethod
    def unregister(cls, source_type: str) -> None:
        """
        Unregister a source type.

        This is primarily for testing purposes.

        Args:
            source_type: Type identifier to unregister.

        Raises:
            ValueError: If source_type is not registered.
        """
        if source_type not in cls._registry:
            raise ValueError(f"Source type '{source_type}' is not registered")

        del cls._registry[source_type]
