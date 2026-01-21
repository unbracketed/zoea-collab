"""
Gemini File Search service for document indexing and retrieval.

DEPRECATED: This module is deprecated. Use file_search.backends.gemini instead.

This module now re-exports GeminiFileSearchStore from file_search for
backwards compatibility. The new implementation provides:
- Common interface via FileSearchStore ABC
- Registry-based backend selection
- Consistent error handling

Migration:
    # Old way (deprecated)
    from documents.gemini_service import GeminiFileSearchService
    service = GeminiFileSearchService()

    # New way (recommended)
    from file_search import FileSearchRegistry
    store = FileSearchRegistry.get('gemini')
    # or
    from file_search.backends import GeminiFileSearchStore
    store = GeminiFileSearchStore()
"""

import warnings

from file_search.backends.gemini import GeminiFileSearchStore

# Re-export with old name for backwards compatibility
GeminiFileSearchService = GeminiFileSearchStore


def __getattr__(name):
    if name == "GeminiFileSearchService":
        warnings.warn(
            "GeminiFileSearchService is deprecated. "
            "Use file_search.backends.GeminiFileSearchStore or "
            "FileSearchRegistry.get('gemini') instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return GeminiFileSearchStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["GeminiFileSearchService", "GeminiFileSearchStore"]
