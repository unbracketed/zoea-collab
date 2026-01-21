"""Content transformation system with factory-based registration.

This package provides a flexible, extensible system for transforming content
between different types and formats. It uses a registry pattern with:

- Factory-based registration (enables dependency injection)
- MRO-aware lookup (parent class transformers work for subclasses)
- Type-safe enum-based format keys
- O(1) lookup with caching

Public API
----------
The main entry points are:

    from transformations import transform, OutputFormat

    # Transform an object to a target format
    result = transform(source_obj, OutputFormat.OUTLINE)

    # With context for dependency injection
    result = transform(
        source_obj,
        OutputFormat.MARKDOWN,
        organization=request.user.organization
    )

Adding New Transformers
-----------------------
To add a new transformer:

    from transformations import register_transformer, OutputFormat
    from transformations.base import BaseTransformer

    @register_transformer(MyModel, OutputFormat.JSON)
    class MyModelToJSONTransformer(BaseTransformer):
        def transform(self, source, **context):
            return {"data": source.some_field}

For dependency injection, use a factory:

    def make_my_transformer():
        service = MyService(api_key=settings.API_KEY)
        return MyTransformer(service=service)

    @register_transformer(MyModel, OutputFormat.CUSTOM, factory=make_my_transformer)
    class MyTransformer(BaseTransformer):
        def __init__(self, service):
            self.service = service

        def transform(self, source, **context):
            return self.service.process(source)
"""

# Import transformers to trigger registration
from . import transformers  # noqa: F401

# Export public API
from .enums import OutputFormat
from .registry import (
    get_available_formats,
    has_transformer,
    register_transformer,
    transform,
)
from .value_objects import (
    ConversationPayload,
    DiagramPayload,
    MarkdownPayload,
    TextPayload,
)

__all__ = [
    # Main API
    "transform",
    "register_transformer",
    "has_transformer",
    "get_available_formats",
    # Enums
    "OutputFormat",
    # Value objects for chaining
    "MarkdownPayload",
    "TextPayload",
    "ConversationPayload",
    "DiagramPayload",
]
