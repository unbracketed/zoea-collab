"""Base classes and protocols for content transformations.

This module provides the core interfaces that all transformers must implement,
along with utility base classes for common transformation patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Protocol, TypeVar

# Type variables for generic transformers
TSource = TypeVar("TSource")
TTarget = TypeVar("TTarget")


class Transformer(Protocol[TSource, TTarget]):
    """Protocol defining the transformer interface.

    All transformers must implement the transform() method which accepts
    a source object and optional context kwargs, returning the transformed result.

    Type Parameters:
        TSource: The input type being transformed
        TTarget: The output type produced by transformation
    """

    def transform(self, source: TSource, **context: Any) -> TTarget:
        """Transform source object to target format.

        Args:
            source: The object to transform (e.g., Markdown, Conversation)
            **context: **Optional** keyword arguments for advanced use cases.
                Most transformations don't need this - source objects already
                contain organization, user, etc. as Django model fields.

                Use context only for:
                - Custom transformation options (e.g., include_toc=True)
                - Value objects without model fields (e.g., MarkdownPayload)
                - Cross-tenant operations (e.g., export_for_org=other_org)
                - External service injection (e.g., services={'diagram': svc})

        Returns:
            The transformed object in the target format

        Raises:
            ValueError: If source object is invalid or missing required fields
        """
        ...


class BaseTransformer(ABC, Generic[TSource, TTarget]):
    """Abstract base class for transformers.

    Provides a concrete base for transformers that prefer inheritance over
    protocol implementation. Useful when transformers need shared initialization
    logic or common helper methods.

    Subclasses must implement transform().
    """

    @abstractmethod
    def transform(self, source: TSource, **context: Any) -> TTarget:
        """Transform source object to target format.

        See Transformer protocol for detailed documentation.
        """
        pass


class TextTransformer(BaseTransformer[TSource, str]):
    """Base class for transformers that produce text output.

    Use this for transformers that output plain text, markdown, JSON strings, etc.
    """

    pass


class DiagramTransformer(BaseTransformer[TSource, dict]):
    """Base class for transformers that produce diagram data structures.

    Use this for transformers that output React Flow, D2, or other
    diagram representation formats.
    """

    pass


class StructuredDataTransformer(BaseTransformer[TSource, dict]):
    """Base class for transformers that produce structured data (dicts/JSON).

    Use this for transformers that output outlines, tree structures,
    or other hierarchical data representations.
    """

    pass


__all__ = [
    "Transformer",
    "BaseTransformer",
    "TextTransformer",
    "DiagramTransformer",
    "StructuredDataTransformer",
    "TSource",
    "TTarget",
]
