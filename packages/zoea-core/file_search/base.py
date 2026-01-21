"""
Abstract base class for File Search Store implementations.

Defines the common interface that all file search backends must implement,
enabling interchangeable use of different search technologies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING

from .types import DocumentReference, SearchResult, StoreInfo

if TYPE_CHECKING:
    from documents.models import Document


class FileSearchStore(ABC):
    """
    Abstract interface for file search backends.

    Implementations must provide methods for:
    - Store lifecycle management (create, get, delete, list)
    - Document operations (add, remove)
    - Search functionality

    Example usage:
        store = FileSearchRegistry.get('gemini')
        store_info = store.create_store('my-store')
        store.add_document(store_info.store_id, document)
        results = store.search(store_info.store_id, 'query')
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """
        Return the backend identifier.

        Returns:
            str: Unique identifier for this backend (e.g., 'gemini', 'chromadb')
        """
        pass

    # -------------------------------------------------------------------------
    # Store Lifecycle
    # -------------------------------------------------------------------------

    @abstractmethod
    def create_store(
        self,
        name: str,
        *,
        ephemeral: bool = False,
    ) -> StoreInfo:
        """
        Create a new store/index.

        Args:
            name: Display name for the store
            ephemeral: If True, store is temporary and should be cleaned up

        Returns:
            StoreInfo with store metadata

        Raises:
            StoreCreationError: If store creation fails
        """
        pass

    @abstractmethod
    def get_store(self, store_id: str) -> StoreInfo | None:
        """
        Get store metadata by ID.

        Args:
            store_id: Backend-specific store identifier

        Returns:
            StoreInfo if found, None otherwise
        """
        pass

    @abstractmethod
    def delete_store(self, store_id: str, *, force: bool = True) -> None:
        """
        Delete a store and all its contents.

        Args:
            store_id: Backend-specific store identifier
            force: If True, delete even if store contains documents

        Raises:
            StoreNotFoundError: If store doesn't exist
            StoreError: If deletion fails
        """
        pass

    @abstractmethod
    def list_stores(self) -> Generator[StoreInfo]:
        """
        List all stores for this backend.

        Yields:
            StoreInfo for each store
        """
        pass

    # -------------------------------------------------------------------------
    # Document Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    def add_document(
        self,
        store_id: str,
        document: Document,
        **options,
    ) -> DocumentReference:
        """
        Add a document to a store.

        Args:
            store_id: Target store identifier
            document: Django Document model instance
            **options: Backend-specific options (e.g., chunking config)

        Returns:
            DocumentReference with the document's location in the store

        Raises:
            StoreNotFoundError: If store doesn't exist
            DocumentUploadError: If upload fails
            UnsupportedDocumentTypeError: If document type not supported
        """
        pass

    @abstractmethod
    def remove_document(self, store_id: str, backend_ref_id: str) -> None:
        """
        Remove a document from a store.

        Args:
            store_id: Store identifier
            backend_ref_id: Backend-specific document reference ID

        Raises:
            StoreNotFoundError: If store doesn't exist
            DocumentNotFoundError: If document not in store
        """
        pass

    @abstractmethod
    def add_text_record(
        self,
        store_id: str,
        *,
        record_id: str,
        content: str,
        metadata: dict,
        display_name: str | None = None,
        **options,
    ) -> DocumentReference:
        """
        Add a raw text record to a store.

        Args:
            store_id: Target store identifier
            record_id: Stable identifier for the record (used for updates)
            content: Text content to index
            metadata: Metadata for filtering/citations
            display_name: Optional display name for the record
            **options: Backend-specific options

        Returns:
            DocumentReference with the record's location in the store
        """
        pass

    @abstractmethod
    def remove_text_record(self, store_id: str, record_id: str) -> None:
        """
        Remove a text record from a store by record ID.

        Args:
            store_id: Store identifier
            record_id: Stable identifier used during indexing
        """
        pass

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    @abstractmethod
    def search(
        self,
        store_id: str,
        query: str,
        *,
        max_results: int = 5,
        filters: dict | None = None,
    ) -> SearchResult:
        """
        Search the store and return results with sources.

        Args:
            store_id: Store to search
            query: Search query string
            max_results: Maximum number of source documents to return
            filters: Optional metadata filters (backend-specific format)

        Returns:
            SearchResult with answer and source citations

        Raises:
            StoreNotFoundError: If store doesn't exist
            SearchError: If search fails
        """
        pass

    # -------------------------------------------------------------------------
    # Helper Methods (optional overrides)
    # -------------------------------------------------------------------------

    def get_document_content(self, document: Document) -> dict:
        """
        Extract content from a document for indexing.

        Default implementation handles common Django document types.
        Backends can override for custom content extraction.

        Args:
            document: Django Document model instance

        Returns:
            dict with 'type' ('file' or 'text') and content info
        """
        from documents.models import (
            PDF,
            FileDocument,
            Image,
            SpreadsheetDocument,
            TextDocument,
            WordDocument,
            YooptaDocument,
        )

        if isinstance(document, Image):
            return {"type": "file", "path": document.image_file.path}
        elif isinstance(document, PDF):
            # Use get_text_content() to extract text via PyMuPDF
            return {"type": "text", "content": document.get_text_content()}
        elif isinstance(document, WordDocument):
            return {"type": "text", "content": document.get_text_content()}
        elif isinstance(document, SpreadsheetDocument):
            return {"type": "text", "content": document.get_text_content()}
        elif isinstance(document, FileDocument):
            return {"type": "file", "path": document.file.path}
        elif isinstance(document, YooptaDocument):
            # Use get_text_content() for better search indexing
            return {"type": "text", "content": document.get_text_content()}
        elif isinstance(document, TextDocument):
            return {"type": "text", "content": document.content or ""}
        elif hasattr(document, "content"):
            return {"type": "text", "content": getattr(document, "content", "")}
        else:
            from .exceptions import UnsupportedDocumentTypeError

            raise UnsupportedDocumentTypeError(
                f"Unsupported document type: {document.get_type_name()}"
            )

    def build_metadata(self, document: Document) -> dict:
        """
        Build metadata dictionary for a document.

        Default implementation extracts common document metadata.
        Backends can override for custom metadata formats.

        Args:
            document: Django Document model instance

        Returns:
            dict with metadata key-value pairs
        """
        metadata = {
            "document_type": document.get_type_name(),
            "organization_id": document.organization_id,
        }

        if document.project_id:
            metadata["project_id"] = document.project_id

        if document.created_at:
            metadata["created_at"] = document.created_at.isoformat()

        if document.created_by:
            metadata["author"] = document.created_by.username
            metadata["author_id"] = document.created_by.id

        return metadata
