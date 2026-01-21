"""
Project Document Search Tool for smolagents.

Provides document search capabilities using the project's file search store.
This tool allows agents to search through indexed project documents
without requiring an explicit RAG session.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from smolagents import Tool

from file_search import FileSearchRegistry

if TYPE_CHECKING:
    from projects.models import Project

logger = logging.getLogger(__name__)


class ProjectDocumentSearchTool(Tool):
    """
    Document search tool using the project's file search store.

    Wraps FileSearchStore to search through project documents
    that have been indexed (PDFs, Word docs, spreadsheets, images, etc.).

    Example:
        tool = ProjectDocumentSearchTool(store_id="projects/123/store")
        result = tool.forward("revenue projections for Q4")
    """

    name = "search_project_documents"
    description = """Searches through documents in this project's knowledge base.
Use this tool to find information from uploaded documents like PDFs, Word documents,
spreadsheets, images, and other files that have been indexed.
Returns relevant excerpts with source citations.
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
        project_id: int | None = None,
        backend: str | None = None,
        **kwargs,
    ):
        """
        Initialize the project document search tool.

        Args:
            store_id: File search store ID for this project
            project_id: Project ID for context in results
            backend: Optional backend name. If not provided, uses registry default.
        """
        super().__init__(**kwargs)
        self.store_id = store_id
        self.project_id = project_id
        self.file_search_store = FileSearchRegistry.get(backend)
        self.telemetry = {
            "calls": 0,
            "errors": 0,
            "total_sources_returned": 0,
            "last_duration_s": None,
        }

    def forward(self, query: str, max_results: int | None = 5) -> str:
        """
        Execute document search against project's file search store.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            Formatted string with retrieved passages and sources
        """
        self.telemetry["calls"] += 1
        start = time.perf_counter()

        try:
            # Build filters for this project
            filters = {}
            if self.project_id:
                filters["project_id"] = str(self.project_id)

            result = self.file_search_store.search(
                store_id=self.store_id,
                query=query,
                max_results=max_results or 5,
                filters=filters if filters else None,
            )

            # Convert SourceReference objects to formatted output
            sources = [
                {
                    "uri": source.uri or "",
                    "title": source.title or "Unknown",
                    "text": source.excerpt or "",
                }
                for source in result.sources
            ]
            self.telemetry["total_sources_returned"] += len(sources)

            return self._format_results(sources)
        except Exception as e:
            self.telemetry["errors"] += 1
            logger.error(f"Project document search error: {e}")
            return f"Error searching documents: {e}"
        finally:
            self.telemetry["last_duration_s"] = time.perf_counter() - start

    def _format_results(self, sources: list[dict]) -> str:
        """Format retrieved sources into a readable string."""
        if not sources:
            return "No relevant documents found in this project's knowledge base."

        parts = ["## Project Documents Found\n"]
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Unknown")
            text = source.get("text", "")
            parts.append(f"\n### [{i}] {title}")
            if text:
                parts.append(f"\n{text}\n")
            parts.append("\n---\n")

        return "".join(parts)


def create_project_document_search_tool(
    project: Project | None = None,
    **kwargs,
) -> ProjectDocumentSearchTool | None:
    """
    Factory function for creating ProjectDocumentSearchTool.

    Called by ToolRegistry with the project context. Returns None if
    the project doesn't have a file search store configured.

    Args:
        project: Project to create the tool for
        **kwargs: Additional configuration (currently unused)

    Returns:
        ProjectDocumentSearchTool instance, or None if no store available
    """
    if project is None:
        logger.debug("No project provided for document search tool")
        return None

    store_id = project.gemini_store_id
    if not store_id:
        logger.debug(
            "Project %s has no file search store configured",
            project.id,
        )
        return None

    logger.debug(
        "Creating document search tool for project %s with store %s",
        project.id,
        store_id,
    )

    return ProjectDocumentSearchTool(
        store_id=store_id,
        project_id=project.id,
    )
