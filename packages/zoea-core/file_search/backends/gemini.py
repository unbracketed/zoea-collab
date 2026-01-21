"""
Gemini File Search backend implementation.

Integrates with Google Gemini's File Search API for creating searchable
document stores and performing RAG-based retrieval.
"""

import os
import tempfile
import time
from collections.abc import Generator

from django.conf import settings
from google import genai
from google.genai import types

from documents.models import Document

from ..base import FileSearchStore
from ..exceptions import (
    DocumentUploadError,
    SearchError,
    StoreCreationError,
    StoreError,
    StoreNotFoundError,
)
from ..registry import FileSearchRegistry
from ..types import DocumentReference, SearchResult, SourceReference, StoreInfo


class GeminiFileSearchStore(FileSearchStore):
    """
    File search backend using Google Gemini File Search API.

    Handles:
    - Creating and managing File Search stores
    - Uploading documents with metadata for filtering and citations
    - Performing RAG-based search queries
    """

    def __init__(self):
        """Initialize Gemini client with API key from settings."""
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise StoreError(
                "GEMINI_API_KEY not found in settings. Please set GEMINI_API_KEY in your .env file."
            )
        self.client = genai.Client(api_key=api_key)

    @property
    def backend_name(self) -> str:
        return "gemini"

    # -------------------------------------------------------------------------
    # Store Lifecycle
    # -------------------------------------------------------------------------

    def create_store(
        self,
        name: str,
        *,
        ephemeral: bool = False,
    ) -> StoreInfo:
        """Create a new Gemini File Search store."""
        try:
            file_search_store = self.client.file_search_stores.create(config={"display_name": name})

            return StoreInfo(
                store_id=file_search_store.name,
                display_name=name,
                backend=self.backend_name,
                ephemeral=ephemeral,
            )
        except Exception as e:
            raise StoreCreationError(f"Failed to create File Search store: {e}") from e

    def get_store(self, store_id: str) -> StoreInfo | None:
        """Get store metadata by ID."""
        try:
            store = self.client.file_search_stores.get(name=store_id)
            return StoreInfo(
                store_id=store.name,
                display_name=store.display_name or store_id,
                backend=self.backend_name,
            )
        except Exception:
            return None

    def delete_store(self, store_id: str, *, force: bool = True) -> None:
        """Delete a Gemini File Search store."""
        try:
            self.client.file_search_stores.delete(name=store_id, config={"force": force})
        except Exception as e:
            if "not found" in str(e).lower():
                raise StoreNotFoundError(f"Store not found: {store_id}") from e
            raise StoreError(f"Failed to delete File Search store: {e}") from e

    def list_stores(self) -> Generator[StoreInfo]:
        """List all Gemini File Search stores."""
        for store in self.client.file_search_stores.list():
            yield StoreInfo(
                store_id=store.name,
                display_name=store.display_name or store.name,
                backend=self.backend_name,
            )

    # -------------------------------------------------------------------------
    # Document Operations
    # -------------------------------------------------------------------------

    def add_document(
        self,
        store_id: str,
        document: Document,
        **options,
    ) -> DocumentReference:
        """
        Upload a document to a Gemini File Search store.

        Options:
            max_tokens_per_chunk: Maximum tokens per chunk (default: 200)
            max_overlap_tokens: Overlap between chunks (default: 20)
        """
        max_tokens_per_chunk = options.get("max_tokens_per_chunk", 200)
        max_overlap_tokens = options.get("max_overlap_tokens", 20)

        # Get document content
        content_info = self.get_document_content(document)

        # Build metadata for Gemini format
        metadata = self._build_gemini_metadata(document)

        try:
            if content_info["type"] == "file":
                operation = self._upload_file(
                    store_id=store_id,
                    file_path=content_info["path"],
                    display_name=document.name,
                    metadata=metadata,
                    max_tokens_per_chunk=max_tokens_per_chunk,
                    max_overlap_tokens=max_overlap_tokens,
                )
            else:
                operation = self._upload_text(
                    store_id=store_id,
                    content=content_info["content"],
                    display_name=document.name,
                    metadata=metadata,
                    max_tokens_per_chunk=max_tokens_per_chunk,
                    max_overlap_tokens=max_overlap_tokens,
                )

            # Wait for upload to complete
            while not operation.done:
                time.sleep(2)
                operation = self.client.operations.get(operation)

            # Extract file ID from operation response
            file_id = None
            if hasattr(operation, "response") and operation.response:
                file_id = getattr(operation.response, "name", None)

            return DocumentReference(
                document_id=document.id,
                store_id=store_id,
                backend_ref_id=file_id or f"doc-{document.id}",
                display_name=document.name,
            )

        except Exception as e:
            raise DocumentUploadError(f"Failed to upload document '{document.name}': {e}") from e

    def _upload_file(
        self,
        store_id: str,
        file_path: str,
        display_name: str,
        metadata: list,
        max_tokens_per_chunk: int,
        max_overlap_tokens: int,
    ):
        """Upload a file to the store."""
        return self.client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store_id,
            config={
                "display_name": display_name,
                "custom_metadata": metadata,
                "chunking_config": {
                    "white_space_config": {
                        "max_tokens_per_chunk": max_tokens_per_chunk,
                        "max_overlap_tokens": max_overlap_tokens,
                    }
                },
            },
        )

    def _upload_text(
        self,
        store_id: str,
        content: str,
        display_name: str,
        metadata: list,
        max_tokens_per_chunk: int,
        max_overlap_tokens: int,
    ):
        """Upload text content to the store via temp file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            return self.client.file_search_stores.upload_to_file_search_store(
                file=temp_path,
                file_search_store_name=store_id,
                config={
                    "display_name": display_name,
                    "custom_metadata": metadata,
                    "chunking_config": {
                        "white_space_config": {
                            "max_tokens_per_chunk": max_tokens_per_chunk,
                            "max_overlap_tokens": max_overlap_tokens,
                        }
                    },
                },
            )
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def remove_document(self, store_id: str, backend_ref_id: str) -> None:
        """
        Remove a document from a Gemini store.

        Note: Gemini File Search API may not support individual file removal.
        This is a placeholder for future API support.
        """
        # TODO: Implement when Gemini API supports file removal
        pass

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
        """Add a raw text record to a Gemini store."""
        max_tokens_per_chunk = options.get("max_tokens_per_chunk", 200)
        max_overlap_tokens = options.get("max_overlap_tokens", 20)
        metadata_entries = self._build_generic_metadata(metadata)

        try:
            operation = self._upload_text(
                store_id=store_id,
                content=content,
                display_name=display_name or record_id,
                metadata=metadata_entries,
                max_tokens_per_chunk=max_tokens_per_chunk,
                max_overlap_tokens=max_overlap_tokens,
            )

            while not operation.done:
                time.sleep(2)
                operation = self.client.operations.get(operation)

            file_id = None
            if hasattr(operation, "response") and operation.response:
                file_id = getattr(operation.response, "name", None)

            return DocumentReference(
                document_id=None,
                store_id=store_id,
                backend_ref_id=file_id or record_id,
                display_name=display_name or record_id,
            )
        except Exception as e:
            raise DocumentUploadError(f"Failed to upload record '{record_id}': {e}") from e

    def remove_text_record(self, store_id: str, record_id: str) -> None:
        """Remove a text record from a Gemini store."""
        # Gemini File Search API does not yet support per-file removal.
        pass

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        store_id: str,
        query: str,
        *,
        max_results: int = 5,
        filters: dict | None = None,
    ) -> SearchResult:
        """Search the store using Gemini's RAG capabilities."""
        file_search_config = {"file_search_store_names": [store_id]}

        # Add metadata filter if provided
        if filters and "metadata_filter" in filters:
            file_search_config["metadata_filter"] = filters["metadata_filter"]

        try:
            response = self.client.models.generate_content(
                model=getattr(settings, "GEMINI_MODEL_ID", "gemini-2.0-flash"),
                contents=query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(file_search=types.FileSearch(**file_search_config))]
                ),
            )

            # Extract sources from grounding metadata
            sources = self._extract_sources(response, max_results)

            # Get the response text
            answer = ""
            if response.text:
                answer = response.text

            return SearchResult(
                answer=answer,
                sources=sources,
                raw_response=response,
            )

        except Exception as e:
            raise SearchError(f"Failed to search File Search store: {e}") from e

    def _extract_sources(self, response, max_results: int) -> list[SourceReference]:
        """Extract source documents from Gemini grounding metadata."""
        sources = []

        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            grounding = getattr(candidate, "grounding_metadata", None)

            if grounding and hasattr(grounding, "grounding_chunks"):
                for chunk in grounding.grounding_chunks or []:
                    if len(sources) >= max_results:
                        break

                    if hasattr(chunk, "retrieved_context"):
                        ctx = chunk.retrieved_context
                        sources.append(
                            SourceReference(
                                title=getattr(ctx, "title", None),
                                uri=getattr(ctx, "uri", None),
                                excerpt=getattr(ctx, "text", None),
                            )
                        )

        return sources

    # -------------------------------------------------------------------------
    # Gemini-specific helpers
    # -------------------------------------------------------------------------

    def _build_gemini_metadata(self, document: Document) -> list:
        """
        Build metadata in Gemini's expected format.

        Returns list of dicts with 'key' and 'string_value' or 'numeric_value'.
        """
        metadata = []

        metadata.append({"key": "document_type", "string_value": document.get_type_name()})
        metadata.append({"key": "organization_id", "numeric_value": document.organization_id})

        if document.project_id:
            metadata.append({"key": "project_id", "numeric_value": document.project_id})

        if document.created_at:
            metadata.append({"key": "created_at", "string_value": document.created_at.isoformat()})

        if document.created_by:
            metadata.append({"key": "author", "string_value": document.created_by.username})
            metadata.append({"key": "author_id", "numeric_value": document.created_by.id})

        return metadata

    def _build_generic_metadata(self, metadata: dict) -> list:
        """Convert a metadata dict to Gemini custom_metadata entries."""
        entries = []
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, (int, float)):
                entries.append({"key": key, "numeric_value": value})
            else:
                entries.append({"key": key, "string_value": str(value)})
        return entries

    # -------------------------------------------------------------------------
    # Legacy compatibility methods
    # -------------------------------------------------------------------------

    def create_or_get_store(self, project) -> dict:
        """
        Legacy method: Create or get store for a project.

        Maintains compatibility with existing code that uses this pattern.
        """
        if project.gemini_store_id:
            store_info = self.get_store(project.gemini_store_id)
            if store_info:
                return {"name": store_info.store_id, "display_name": store_info.display_name}
            # Store was deleted, clear project reference
            project.gemini_store_id = None
            project.gemini_store_name = None

        # Create new store
        store_display_name = f"{project.organization.name} - {project.name}"
        store_info = self.create_store(store_display_name)

        # Update project with store information
        project.gemini_store_id = store_info.store_id
        project.gemini_store_name = store_display_name
        project.save(update_fields=["gemini_store_id", "gemini_store_name"])

        return {"name": store_info.store_id, "display_name": store_display_name}

    def create_ephemeral_store(self, display_name: str) -> dict:
        """
        Legacy method: Create an ephemeral store.

        Maintains compatibility with existing RAG session code.
        """
        store_info = self.create_store(display_name, ephemeral=True)
        return {"name": store_info.store_id, "display_name": store_info.display_name}

    def upload_document(
        self,
        document: Document,
        store_id: str,
        max_tokens_per_chunk: int = 200,
        max_overlap_tokens: int = 20,
    ) -> dict:
        """
        Legacy method: Upload document with old return format.

        Maintains compatibility with existing sync command.
        """
        ref = self.add_document(
            store_id=store_id,
            document=document,
            max_tokens_per_chunk=max_tokens_per_chunk,
            max_overlap_tokens=max_overlap_tokens,
        )
        return {
            "operation": None,  # No longer exposed
            "file_id": ref.backend_ref_id,
            "display_name": ref.display_name,
        }

    def query_store(
        self,
        store_id: str,
        query: str,
        *,
        model_id: str | None = None,
        metadata_filter: str | None = None,
    ):
        """
        Legacy method: Query store with raw Gemini response.

        For new code, use search() which returns SearchResult.
        """
        file_search_config = {"file_search_store_names": [store_id]}

        if metadata_filter:
            file_search_config["metadata_filter"] = metadata_filter

        return self.client.models.generate_content(
            model=model_id or getattr(settings, "GEMINI_MODEL_ID", "gemini-2.0-flash"),
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(file_search=types.FileSearch(**file_search_config))]
            ),
        )


# Register as default backend
FileSearchRegistry.register("gemini", GeminiFileSearchStore, set_default=True)
