"""
File Search Store - Unified interface for document search backends.

This module provides an abstraction layer for file search/retrieval operations,
allowing different backends (Gemini File Search, ChromaDB, etc.) to be used
interchangeably through a common interface.

Example usage:
    from file_search import FileSearchRegistry, SearchResult

    # Get the configured backend
    store = FileSearchRegistry.get()

    # Create a store
    store_info = store.create_store('my-project-store')

    # Add documents
    store.add_document(store_info.store_id, document)

    # Search
    result = store.search(store_info.store_id, 'find relevant info')
    print(result.answer)
    for source in result.sources:
        print(f"  - {source.title}: {source.excerpt}")

    # Cleanup
    store.delete_store(store_info.store_id)
"""

from .base import FileSearchStore
from .exceptions import (
    BackendError,
    BackendNotFoundError,
    ConfigurationError,
    DocumentError,
    DocumentNotFoundError,
    DocumentUploadError,
    FileSearchError,
    SearchError,
    StoreCreationError,
    StoreError,
    StoreNotFoundError,
    UnsupportedDocumentTypeError,
)
from .registry import FileSearchRegistry
from .types import DocumentContent, DocumentReference, SearchResult, SourceReference, StoreInfo


def _ensure_backends_registered():
    """Lazy import of backends to avoid circular imports during Django setup."""
    from . import backends  # noqa: F401


# Register backends lazily when registry is first accessed
FileSearchRegistry._ensure_backends = _ensure_backends_registered

__all__ = [
    # Core classes
    "FileSearchStore",
    "FileSearchRegistry",
    # Types
    "SearchResult",
    "SourceReference",
    "StoreInfo",
    "DocumentContent",
    "DocumentReference",
    # Exceptions
    "FileSearchError",
    "StoreError",
    "StoreNotFoundError",
    "StoreCreationError",
    "DocumentError",
    "DocumentUploadError",
    "DocumentNotFoundError",
    "UnsupportedDocumentTypeError",
    "SearchError",
    "BackendError",
    "ConfigurationError",
    "BackendNotFoundError",
]
