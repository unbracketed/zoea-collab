"""Transformer registry with factory-based registration and MRO-aware lookup.

This module provides the core infrastructure for registering and invoking
content transformations. It supports:

- Factory-based registration (enables dependency injection)
- MRO-aware registration (transformers registered for parent classes work for subclasses)
- O(1) lookup with caching (no repeated scans)
- Type-safe format enum keys
- Context passing for dependencies
"""

import inspect
from typing import Any, Callable, Optional, Type

from .base import Transformer
from .enums import OutputFormat

# Type alias for transformer factories
# Can be either a class or a callable that returns a Transformer instance
TransformerFactory = Callable[[], Transformer]

# Registry maps (source_type, output_format) -> factory
_REGISTRY: dict[tuple[Type, OutputFormat], TransformerFactory] = {}

# Cache for resolved concrete types to avoid repeated MRO walks
_RESOLVED_CACHE: dict[tuple[Type, OutputFormat], TransformerFactory] = {}


def register_transformer(
    source_type: Type,
    output_format: OutputFormat,
    *,
    factory: Optional[TransformerFactory] = None,
) -> Callable:
    """Decorator to register a transformer factory for a source type and output format.

    This decorator registers a transformer by walking the source_type's MRO (Method
    Resolution Order) and inserting entries for each ancestor class. This enables
    transformers registered for parent classes to automatically work for subclasses,
    while still allowing subclasses to override with more specific transformers.

    Args:
        source_type: The type of object that can be transformed
        output_format: The target output format (from OutputFormat enum)
        factory: Optional factory callable. If None, uses the decorated class.
            The factory should return a new Transformer instance each time it's called.

    Returns:
        The decorator function

    Raises:
        ValueError: If attempting to register a duplicate transformer for the
            same (source_type, output_format) pair

    Examples:
        # Register a class (class itself is the factory)
        @register_transformer(Markdown, OutputFormat.OUTLINE)
        class MarkdownToOutlineTransformer(BaseTransformer):
            def transform(self, source, **context):
                return parse_outline(source.content)

        # Register with a custom factory (for dependency injection)
        def make_graphologue_transformer():
            service = GraphologueService(api_key=settings.OPENAI_API_KEY)
            return ConversationToGraphologueTransformer(service=service)

        register_transformer(
            Conversation,
            OutputFormat.REACTFLOW,
            factory=make_graphologue_transformer
        )(make_graphologue_transformer)  # decorator still needs a target

        # Or use as a regular function
        class MyTransformer(BaseTransformer):
            pass

        register_transformer(
            MyModel,
            OutputFormat.JSON,
            factory=lambda: MyTransformer()
        )(MyTransformer)
    """

    def decorator(cls_or_factory: Any) -> Any:
        # Determine the actual factory
        actual_factory = factory if factory is not None else cls_or_factory

        # Ensure factory is callable
        if not callable(actual_factory):
            raise TypeError(
                f"Transformer factory must be callable, got {type(actual_factory)}"
            )

        # Walk the MRO and register for each ancestor (except object)
        for ancestor in inspect.getmro(source_type):
            if ancestor is object:
                continue

            key = (ancestor, output_format)

            # For the exact source_type being registered
            if ancestor is source_type:
                # Check for duplicate registration
                if key in _REGISTRY:
                    raise ValueError(
                        f"Transformer already registered for {source_type.__name__} "
                        f"-> {output_format.value}. "
                        f"Each (source_type, output_format) pair can only be "
                        f"registered once."
                    )
                # Always register for the exact type
                _REGISTRY[key] = actual_factory
            else:
                # For ancestors, only register if no more specific transformer exists
                # This allows subclasses to override parent transformers
                if key not in _REGISTRY:
                    _REGISTRY[key] = actual_factory

        # Clear the resolved cache since we've added new transformers
        _RESOLVED_CACHE.clear()

        return cls_or_factory

    return decorator


def transform(source: Any, output_format: OutputFormat, **context: Any) -> Any:
    """Transform a source object to the specified output format.

    This is the main public API for performing transformations. It looks up
    the appropriate transformer based on the source object's type and the
    requested output format, then invokes it with the provided context.

    Args:
        source: The object to transform
        output_format: The desired output format (from OutputFormat enum)
        **context: Additional dependencies or configuration for the transformation.
            Common context keys:
            - organization: For tenant-aware transformations
            - user: For permission checking
            - services: Dict of injected service instances

    Returns:
        The transformed object in the target format

    Raises:
        ValueError: If no transformer is registered for the source type and format
        TypeError: If the output_format is not an OutputFormat enum value

    Examples:
        from transformations import transform, OutputFormat

        # Simple transformation
        outline = transform(markdown_doc, OutputFormat.OUTLINE)

        # With context for dependency injection
        diagram = transform(
            conversation,
            OutputFormat.REACTFLOW,
            organization=request.user.organization,
            user=request.user
        )
    """
    if not isinstance(output_format, OutputFormat):
        raise TypeError(
            f"output_format must be an OutputFormat enum value, "
            f"got {type(output_format).__name__}: {output_format}"
        )

    source_type = type(source)
    cache_key = (source_type, output_format)

    # Check resolved cache first
    factory = _RESOLVED_CACHE.get(cache_key)

    if factory is None:
        # Try exact match first (O(1))
        factory = _REGISTRY.get(cache_key)

        # If no exact match, walk the MRO to find a parent class transformer
        if factory is None:
            for ancestor in inspect.getmro(source_type):
                if ancestor is object:
                    continue
                ancestor_key = (ancestor, output_format)
                factory = _REGISTRY.get(ancestor_key)
                if factory is not None:
                    break

        if factory is None:
            # Generate helpful error message
            available = _get_available_formats(source_type)
            available_str = ", ".join(fmt.value for fmt in available) if available else "none"

            raise ValueError(
                f"No transformer registered for {source_type.__name__} "
                f"-> {output_format.value}\n"
                f"Available formats for {source_type.__name__}: {available_str}\n"
                f"Check that a transformer is registered using "
                f"@register_transformer({source_type.__name__}, OutputFormat.{output_format.name})"
            )

        # Cache the resolved factory
        _RESOLVED_CACHE[cache_key] = factory

    # Instantiate transformer from factory and invoke
    transformer = factory()
    return transformer.transform(source, **context)


def has_transformer(source_type: Type, output_format: OutputFormat) -> bool:
    """Check if a transformer is registered for the given source type and format.

    Useful for guard checks before attempting a transformation.

    Args:
        source_type: The type to check
        output_format: The output format to check

    Returns:
        True if a transformer is registered, False otherwise

    Example:
        if has_transformer(Markdown, OutputFormat.OUTLINE):
            outline = transform(markdown_doc, OutputFormat.OUTLINE)
        else:
            # Handle missing transformer
            pass
    """
    return (source_type, output_format) in _REGISTRY


def get_available_formats(source_type: Type) -> list[OutputFormat]:
    """Get all registered output formats for a source type.

    Args:
        source_type: The type to check

    Returns:
        List of OutputFormat values that have registered transformers

    Example:
        formats = get_available_formats(Markdown)
        # [OutputFormat.OUTLINE, OutputFormat.JSON, OutputFormat.MARKDOWN]
    """
    return _get_available_formats(source_type)


def _get_available_formats(source_type: Type) -> list[OutputFormat]:
    """Internal helper to get available formats."""
    return sorted(
        {fmt for (typ, fmt) in _REGISTRY.keys() if typ == source_type},
        key=lambda f: f.value,
    )


def clear_registry() -> None:
    """Clear all registered transformers.

    Primarily useful for testing. In production, transformers are registered
    at import time and remain registered for the application lifetime.
    """
    _REGISTRY.clear()
    _RESOLVED_CACHE.clear()


__all__ = [
    "register_transformer",
    "transform",
    "has_transformer",
    "get_available_formats",
    "clear_registry",
]
