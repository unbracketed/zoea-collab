"""
ChromaDB File Search backend implementation.

Provides a local vector database backend for document search,
useful for development and testing without requiring external API keys.
"""

import logging
from collections.abc import Generator

from django.conf import settings

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

logger = logging.getLogger(__name__)


class ChromaDBFileSearchStore(FileSearchStore):
    """
    File search backend using ChromaDB for local development.

    ChromaDB is an open-source embedding database that runs locally,
    making it ideal for development without external dependencies.

    Note: This backend uses ChromaDB's built-in embedding function.
    For production use with similar quality to Gemini, consider
    using an OpenAI embedding function.
    """

    def __init__(self, persist_directory: str | None = None):
        """
        Initialize ChromaDB client.

        Args:
            persist_directory: Optional path to persist the database.
                              If not provided, uses in-memory storage.
        """
        try:
            import chromadb
        except ImportError as e:
            raise StoreError("ChromaDB is not installed. Install with: pip install chromadb") from e

        persist_directory = persist_directory or getattr(
            settings, "CHROMADB_PERSIST_DIRECTORY", None
        )

        if persist_directory:
            self.client = chromadb.PersistentClient(path=str(persist_directory))
        else:
            self.client = chromadb.Client()

        self._stores: dict[str, str] = {}  # store_id -> display_name mapping

    @property
    def backend_name(self) -> str:
        return "chromadb"

    # -------------------------------------------------------------------------
    # Store Lifecycle
    # -------------------------------------------------------------------------

    def create_store(
        self,
        name: str,
        *,
        ephemeral: bool = False,
    ) -> StoreInfo:
        """Create a new ChromaDB collection."""
        try:
            # Generate a unique store ID
            store_id = self._generate_store_id(name)

            # Create collection with metadata
            self.client.get_or_create_collection(
                name=store_id,
                metadata={"display_name": name, "ephemeral": str(ephemeral)},
            )

            self._stores[store_id] = name

            return StoreInfo(
                store_id=store_id,
                display_name=name,
                backend=self.backend_name,
                ephemeral=ephemeral,
            )
        except Exception as e:
            raise StoreCreationError(f"Failed to create ChromaDB collection: {e}") from e

    def get_store(self, store_id: str) -> StoreInfo | None:
        """Get store metadata by ID."""
        try:
            collection = self.client.get_collection(name=store_id)
            metadata = collection.metadata or {}
            return StoreInfo(
                store_id=store_id,
                display_name=metadata.get("display_name", store_id),
                backend=self.backend_name,
                document_count=collection.count(),
                ephemeral=metadata.get("ephemeral") == "True",
            )
        except Exception:
            return None

    def delete_store(self, store_id: str, *, force: bool = True) -> None:
        """Delete a ChromaDB collection."""
        try:
            self.client.delete_collection(name=store_id)
            self._stores.pop(store_id, None)
        except Exception as e:
            if "does not exist" in str(e).lower():
                raise StoreNotFoundError(f"Store not found: {store_id}") from e
            raise StoreError(f"Failed to delete ChromaDB collection: {e}") from e

    def list_stores(self) -> Generator[StoreInfo]:
        """List all ChromaDB collections."""
        for collection in self.client.list_collections():
            metadata = collection.metadata or {}
            yield StoreInfo(
                store_id=collection.name,
                display_name=metadata.get("display_name", collection.name),
                backend=self.backend_name,
                document_count=collection.count(),
                ephemeral=metadata.get("ephemeral") == "True",
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
        Add a document to a ChromaDB collection.

        Documents are chunked and embedded using ChromaDB's default
        embedding function.
        """
        try:
            collection = self.client.get_collection(name=store_id)
        except Exception as e:
            raise DocumentUploadError(f"Collection not found: {store_id}") from e

        text_content = self._extract_document_text(document)
        if not text_content:
            raise DocumentUploadError(f"Document '{document.name}' has no indexable text")

        metadata = options.get("metadata") or {
            "document_id": str(document.id),
            "document_name": document.name,
            "document_type": document.get_type_name(),
            "organization_id": str(document.organization_id),
            "project_id": str(document.project_id) if document.project_id else "",
        }

        record_id = f"doc-{document.id}"
        try:
            self.add_text_record(
                store_id,
                record_id=record_id,
                content=text_content,
                metadata=metadata,
                display_name=document.name,
            )
        except Exception as e:
            raise DocumentUploadError(f"Failed to add document '{document.name}': {e}") from e

        return DocumentReference(
            document_id=document.id,
            store_id=store_id,
            backend_ref_id=record_id,
            display_name=document.name,
        )

    def remove_document(self, store_id: str, backend_ref_id: str) -> None:
        """Remove a document from a ChromaDB collection."""
        self.remove_text_record(store_id, backend_ref_id)

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
        """Add a text record to a ChromaDB collection."""
        if not content:
            raise DocumentUploadError("Cannot index empty content")

        try:
            collection = self.client.get_collection(name=store_id)
        except Exception as e:
            raise DocumentUploadError(f"Collection not found: {store_id}") from e

        normalized = self._normalize_metadata(metadata)
        normalized["record_id"] = record_id
        if display_name:
            normalized["record_name"] = display_name

        chunks = self._chunk_text(content)
        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            ids.append(f"{record_id}-chunk-{i}")
            documents.append(chunk)
            chunk_meta = dict(normalized)
            chunk_meta["chunk_index"] = str(i)
            metadatas.append(chunk_meta)

        try:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
        except Exception as e:
            raise DocumentUploadError(f"Failed to add record '{record_id}': {e}") from e

        return DocumentReference(
            document_id=None,
            store_id=store_id,
            backend_ref_id=record_id,
            display_name=display_name or record_id,
        )

    def remove_text_record(self, store_id: str, record_id: str) -> None:
        """Remove a text record from a ChromaDB collection."""
        try:
            collection = self.client.get_collection(name=store_id)
            collection.delete(where={"record_id": record_id})
        except Exception as e:
            logger.warning("Failed to remove record %s: %s", record_id, e)

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
        """Search the collection using semantic similarity."""
        try:
            collection = self.client.get_collection(name=store_id)
        except Exception as e:
            raise SearchError(f"Collection not found: {store_id}") from e

        try:
            # Build where filter if provided
            where_filter = None
            if filters:
                where_filter = filters.get("where")

            # Query the collection
            results = collection.query(
                query_texts=[query],
                n_results=max_results,
                where=where_filter,
            )

            # Convert results to SearchResult format
            sources = []
            seen_docs: set[str] = set()

            if results["documents"] and results["documents"][0]:
                for i, doc_text in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    record_id = metadata.get("record_id") or metadata.get("document_id") or ""

                    # Deduplicate by record/document
                    if record_id and record_id in seen_docs:
                        continue
                    if record_id:
                        seen_docs.add(record_id)

                    # Calculate relevance score from distance
                    distance = results["distances"][0][i] if results["distances"] else 0
                    relevance = 1 - distance

                    sources.append(
                        SourceReference(
                            document_id=int(metadata.get("document_id"))
                            if metadata.get("document_id")
                            else None,
                            title=metadata.get("document_name") or metadata.get("record_name"),
                            excerpt=doc_text[:500] if doc_text else None,
                            relevance_score=relevance,
                            metadata=metadata,
                        )
                    )

            # Generate a simple answer based on retrieved content
            answer = self._generate_answer(query, sources)

            return SearchResult(
                answer=answer,
                sources=sources,
                raw_response=results,
            )

        except Exception as e:
            raise SearchError(f"Search failed: {e}") from e

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _generate_store_id(self, name: str) -> str:
        """Generate a unique, valid ChromaDB collection name."""
        import time

        # ChromaDB collection names must be alphanumeric with underscores
        base = "".join(c if c.isalnum() else "_" for c in name.lower())
        timestamp = hex(int(time.time() * 1000))[-8:]
        return f"{base[:50]}_{timestamp}"

    def _chunk_text(self, text: str, max_chunk_size: int = 1000) -> list[str]:
        """
        Simple text chunking by paragraphs.

        For production use, consider more sophisticated chunking strategies.
        """
        if not text:
            return []

        # Split by double newlines (paragraphs)
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            if current_size + para_size > max_chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text[:max_chunk_size]]

    def _extract_document_text(self, document: Document) -> str:
        """Extract text content from a Django Document for indexing."""
        content_info = self.get_document_content(document)

        if content_info["type"] == "file":
            try:
                with open(content_info["path"], encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception as e:
                raise DocumentUploadError(f"Cannot read file: {e}") from e

        return content_info["content"]

    def _normalize_metadata(self, metadata: dict) -> dict:
        """Normalize metadata values to ChromaDB-compatible primitives."""
        normalized = {}
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, (bool, int, float)):
                normalized[key] = value
            else:
                normalized[key] = str(value)
        return normalized

    def _generate_answer(self, query: str, sources: list[SourceReference]) -> str:
        """
        Generate a simple answer based on retrieved sources.

        Note: For production, you'd want to use an LLM here.
        ChromaDB is just for vector search, not RAG generation.
        """
        if not sources:
            return "No relevant documents found for your query."

        # Simple answer: concatenate relevant excerpts
        excerpts = []
        for source in sources[:3]:  # Limit to top 3
            if source.excerpt:
                excerpts.append(f"From '{source.title}':\n{source.excerpt}")

        if excerpts:
            return "Based on the documents in this collection:\n\n" + "\n\n---\n\n".join(excerpts)

        return "Found relevant documents but could not extract content."


# Register the backend (but don't set as default - Gemini is default)
FileSearchRegistry.register("chromadb", ChromaDBFileSearchStore, set_default=False)
