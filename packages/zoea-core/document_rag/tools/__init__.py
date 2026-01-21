"""
smolagents tools for Document RAG.

DEPRECATED: This module is maintained for backward compatibility.
Import from agents.tools instead:

    from agents.tools import DocumentRetrieverTool, ImageAnalyzerTool

This module provides custom tools that wrap existing services:
- DocumentRetrieverTool: Wraps FileSearchStore for document retrieval (backend-agnostic)
- ImageAnalyzerTool: Vision model for image document analysis
- GeminiRetrieverTool: Deprecated alias for DocumentRetrieverTool
"""

import warnings

# Import from new canonical location for backward compatibility
from agents.tools.document_retriever import DocumentRetrieverTool, GeminiRetrieverTool
from agents.tools.image_analyzer import ImageAnalyzerTool

__all__ = ["DocumentRetrieverTool", "GeminiRetrieverTool", "ImageAnalyzerTool"]


def __getattr__(name):
    """Emit deprecation warning when accessing tools from this module."""
    if name in __all__:
        warnings.warn(
            f"Importing {name} from document_rag.tools is deprecated. "
            f"Use 'from agents.tools import {name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Return the already-imported class
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
