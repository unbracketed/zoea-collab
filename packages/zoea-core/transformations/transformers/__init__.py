"""Concrete transformer implementations.

This package contains all the transformer classes that convert various content
types to different output formats. Each module is organized by source type:

- markdown.py: Transformers for Markdown documents
- conversation.py: Transformers for Conversation objects
- document.py: Transformers for other Document types (PDF, Image, etc.)

All transformers are automatically registered via the @register_transformer
decorator when this package is imported.
"""

# Import all transformer modules to trigger registration
# This ensures all transformers are available when the transformations
# package is imported
from . import conversation, markdown  # noqa: F401

__all__ = ["markdown", "conversation"]
