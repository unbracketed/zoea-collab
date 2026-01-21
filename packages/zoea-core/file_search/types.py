"""
Type definitions for File Search Store interface.

These dataclasses provide a standardized representation of search results,
source references, and store metadata across all backend implementations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SourceReference:
    """
    Reference to a source document retrieved during search.

    Represents a citation to a document that contributed to the search result.
    """

    document_id: int | None = None
    title: str | None = None
    uri: str | None = None
    excerpt: str | None = None
    relevance_score: float | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResult:
    """
    Standardized search result across all backends.

    Contains the generated answer/response along with source citations
    and optional backend-specific raw response data.
    """

    answer: str
    sources: list[SourceReference] = field(default_factory=list)
    raw_response: Any | None = None


@dataclass
class StoreInfo:
    """
    Metadata about a file search store/index.

    Provides information about a store's identity and state.
    """

    store_id: str
    display_name: str
    backend: str
    document_count: int | None = None
    created_at: datetime | None = None
    ephemeral: bool = False


@dataclass
class DocumentContent:
    """
    Extracted content from a document for indexing.

    Represents the content to be indexed, either as a file path
    or as text content directly.
    """

    content_type: str  # 'file' or 'text'
    file_path: str | None = None
    text_content: str | None = None
    mime_type: str | None = None


@dataclass
class DocumentReference:
    """
    Reference to a document or record within a store.

    Returned after adding content to track its location in the store.
    """

    document_id: int | None
    store_id: str
    backend_ref_id: str  # Backend-specific reference ID
    display_name: str
