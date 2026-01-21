"""
Document Retriever Tool for smolagents.

Wraps FileSearchStore implementations as a smolagents Tool for document retrieval.
Backend-agnostic: works with any FileSearchStore implementation (Gemini, ChromaDB, etc.).

Migrated from document_rag/tools/document_retriever.py
"""

import logging
import time
from typing import Optional

from smolagents import Tool

from file_search import FileSearchRegistry

logger = logging.getLogger(__name__)


class DocumentRetrieverTool(Tool):
    """
    smolagents Tool wrapping file search backends for document retrieval.

    This tool allows the CodeAgent to search through indexed documents
    and retrieve relevant passages with source citations. Works with
    any registered FileSearchStore backend.

    Example:
        tool = DocumentRetrieverTool(store_id="projects/123/stores/abc")
        result = tool.forward("How to configure authentication?")
    """

    name = "document_retriever"
    description = """Retrieves relevant passages from the indexed documents.
Use this tool to find information related to the user's question.
Returns excerpts from documents with source citations.
Use declarative statements rather than questions for better results."""

    inputs = {
        "query": {
            "type": "string",
            "description": (
                "Search query to find relevant document passages. "
                "Use declarative statements rather than questions for better results."
            ),
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default: 5)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(
        self,
        store_id: str,
        backend: Optional[str] = None,
        filters: dict | None = None,
        **kwargs,
    ):
        """
        Initialize the retriever tool.

        Args:
            store_id: File search store ID for this session
            backend: Optional backend name. If not provided, uses registry default.
        """
        super().__init__(**kwargs)
        self.store_id = store_id
        self.file_search_store = FileSearchRegistry.get(backend)
        self.filters = filters
        self.last_retrieved_sources: list[dict] = []
        self.telemetry = {
            "calls": 0,
            "errors": 0,
            "total_sources_returned": 0,
            "last_duration_s": None,
        }

    def forward(self, query: str, max_results: Optional[int] = 5) -> str:
        """
        Execute retrieval against file search store.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            Formatted string with retrieved passages and sources
        """
        self.telemetry["calls"] += 1
        start = time.perf_counter()
        try:
            result = self.file_search_store.search(
                store_id=self.store_id,
                query=query,
                max_results=max_results or 5,
                filters=self.filters,
            )

            # Convert SourceReference objects to dicts for storage
            sources = [
                {
                    "uri": source.uri or "",
                    "title": source.title or "Unknown",
                    "text": source.excerpt or "",
                }
                for source in result.sources
            ]
            self.last_retrieved_sources = sources
            self.telemetry["total_sources_returned"] += len(sources)

            return self._format_results(sources)
        except Exception as e:
            self.telemetry["errors"] += 1
            logger.error(f"Document retrieval error: {e}")
            return f"Error retrieving documents: {e}"
        finally:
            self.telemetry["last_duration_s"] = time.perf_counter() - start

    def _format_results(self, sources: list[dict]) -> str:
        """Format retrieved sources into a readable string."""
        if not sources:
            return "No relevant documents found."

        parts = ["Retrieved documents:\n"]
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Unknown")
            text = source.get("text", "")
            parts.append(f"\n[{i}] Source: {title}")
            if text:
                # Include full text content for the agent to use
                parts.append(f"\nContent:\n{text}\n")
            parts.append("\n---\n")

        return "".join(parts)


# Backwards compatibility alias
GeminiRetrieverTool = DocumentRetrieverTool
