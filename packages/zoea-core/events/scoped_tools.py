"""
Scoped tools for skill execution within the harness.

These tools wrap the SkillExecutionHarness APIs to provide safe,
scoped operations that smolagents can use during skill execution.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from smolagents import Tool

if TYPE_CHECKING:
    from events.harness import SkillExecutionHarness

logger = logging.getLogger(__name__)


class ScopedDocumentReaderTool(Tool):
    """
    Read documents within the execution scope.

    Only allows reading documents that belong to the same
    organization (and project, if scoped) as the trigger.
    """

    name = "read_document"
    description = (
        "Read a document by its ID. Only documents within the current "
        "organization/project scope can be accessed."
    )
    inputs = {
        "document_id": {
            "type": "integer",
            "description": "The ID of the document to read",
        }
    }
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self, document_id: int) -> str:
        """Read a document by ID."""
        try:
            doc = self.harness.api.get_document(int(document_id))
            # Get text content if available
            content = ""
            if hasattr(doc, "get_text_content"):
                content = doc.get_text_content()[:10000]
            elif hasattr(doc, "content"):
                content = str(doc.content)[:10000]
            return json.dumps(
                {
                    "id": doc.id,
                    "name": doc.name,
                    "document_type": doc.get_type_name(),
                    "content": content,
                    "created_at": doc.created_at.isoformat(),
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScopedDocumentSearchTool(Tool):
    """
    Search documents using the project's RAG store.

    Only available for project-scoped triggers.
    """

    name = "search_documents"
    description = (
        "Search through documents in the project using semantic search. "
        "Returns relevant document excerpts matching the query."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of results (default: 5)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self, query: str, limit: int | None = None) -> str:
        """Search documents."""
        try:
            results = self.harness.api.search_documents(
                query, limit=limit or 5
            )
            return json.dumps(results)
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScopedDocumentListTool(Tool):
    """
    List documents within the execution scope.
    """

    name = "list_documents"
    description = (
        "List documents in the current project/organization. "
        "Can optionally filter by document type."
    )
    inputs = {
        "document_type": {
            "type": "string",
            "description": "Optional filter by document type (e.g., 'MarkdownDocument')",
            "nullable": True,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of documents to return (default: 20)",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(
        self, document_type: str | None = None, limit: int | None = None
    ) -> str:
        """List documents."""
        try:
            docs = self.harness.api.list_documents(
                document_type=document_type,
                limit=limit or 20,
            )
            return json.dumps(
                [
                    {
                        "id": doc.id,
                        "name": doc.name,
                        "document_type": doc.get_type_name(),
                        "created_at": doc.created_at.isoformat(),
                    }
                    for doc in docs
                ]
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScopedDocumentCreateTool(Tool):
    """
    Create documents within the execution scope.

    Enforces document type allowlist and creation limits.
    """

    name = "create_document"
    description = (
        "Create a new document in the project. The document type must be "
        "in the allowed list (typically: MarkdownDocument, YooptaDocument, TextDocument). "
        "There is a limit on how many documents can be created per run."
    )
    inputs = {
        "document_type": {
            "type": "string",
            "description": "Type of document to create (e.g., 'MarkdownDocument')",
        },
        "name": {
            "type": "string",
            "description": "Name for the new document",
        },
        "content": {
            "type": "string",
            "description": "Content for the document",
        },
    }
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self, document_type: str, name: str, content: str) -> str:
        """Create a document."""
        try:
            doc = self.harness.api.create_document(
                document_type=document_type,
                name=name,
                content=content,
            )
            return json.dumps(
                {
                    "success": True,
                    "id": doc.id,
                    "name": doc.name,
                    "document_type": doc.get_type_name(),
                }
            )
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class ScopedSourceEntityTool(Tool):
    """
    Get information about the source entity that triggered this run.
    """

    name = "get_source_entity"
    description = (
        "Get the source entity (email message, document, etc.) that triggered "
        "this skill execution. Returns details about the triggering event."
    )
    inputs = {}
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self) -> str:
        """Get the source entity."""
        try:
            entity = self.harness.api.get_source_entity()
            source_type = self.harness.context.source_type

            if source_type == "email_message":
                return json.dumps(
                    {
                        "type": "email_message",
                        "id": entity.id,
                        "subject": entity.subject,
                        "sender": entity.sender,
                        "body": entity.stripped_text or entity.body_plain or "",
                        "received_at": entity.received_at.isoformat()
                        if entity.received_at
                        else None,
                    }
                )
            elif source_type == "document":
                # Get content safely
                content = ""
                if hasattr(entity, "get_text_content"):
                    content = entity.get_text_content()[:10000]
                elif hasattr(entity, "content"):
                    content = str(entity.content)[:10000]
                return json.dumps(
                    {
                        "type": "document",
                        "id": entity.id,
                        "name": entity.name,
                        "document_type": entity.get_type_name(),
                        "content": content,
                        "created_at": entity.created_at.isoformat(),
                    }
                )
            else:
                return json.dumps(
                    {
                        "type": source_type,
                        "id": entity.id,
                    }
                )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScopedExternalFetchTool(Tool):
    """
    Fetch data from external URLs (with domain restrictions).

    Only allows fetching from domains in the allowlist.
    """

    name = "fetch_url"
    description = (
        "Fetch content from an external URL. Only allowed domains can be accessed. "
        "Default allowed: duckduckgo.com, wikipedia.org, api.github.com. "
        "Additional domains may be configured per trigger."
    )
    inputs = {
        "url": {
            "type": "string",
            "description": "The URL to fetch",
        },
    }
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self, url: str) -> str:
        """Fetch from URL."""
        import httpx

        try:
            # Check and record the initial URL
            self.harness.external.check_and_record(url)

            # Perform the fetch with redirect limit
            with httpx.Client(timeout=30.0, max_redirects=5) as client:
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Security: Verify final URL after redirects is also allowed
                final_url = str(response.url)
                if final_url != url:
                    # Check if the redirect destination is allowed
                    allowed, reason = self.harness.external.is_allowed(final_url)
                    if not allowed:
                        return json.dumps({
                            "error": f"Redirect to disallowed domain: {reason}",
                            "initial_url": url,
                            "redirect_url": final_url,
                        })

                # Limit response size
                content = response.text[:50000]

                return json.dumps(
                    {
                        "url": final_url,
                        "status_code": response.status_code,
                        "content_type": response.headers.get("content-type", ""),
                        "content": content,
                    }
                )
        except Exception as e:
            return json.dumps({"error": str(e)})


class ScopedProjectInfoTool(Tool):
    """
    Get information about the current project/organization context.
    """

    name = "get_context_info"
    description = (
        "Get information about the current execution context, including "
        "organization name, project name (if scoped), and available document types."
    )
    inputs = {}
    output_type = "string"

    def __init__(self, harness: SkillExecutionHarness, **kwargs):
        super().__init__(**kwargs)
        self.harness = harness

    def forward(self) -> str:
        """Get context info."""
        try:
            org = self.harness.organization
            project = self.harness.project

            return json.dumps(
                {
                    "organization": {
                        "id": org.id,
                        "name": org.name,
                    },
                    "project": (
                        {
                            "id": project.id,
                            "name": project.name,
                        }
                        if project
                        else None
                    ),
                    "scope": "project" if project else "organization",
                    "allowed_document_types": list(
                        self.harness.context.allowed_document_types
                    ),
                    "max_documents_per_run": self.harness.context.max_documents_per_run,
                    "documents_created": self.harness.api.audit_log.documents_created,
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})


def create_scoped_tools(harness: SkillExecutionHarness) -> list[Tool]:
    """
    Create all scoped tools for a harness.

    Args:
        harness: The execution harness

    Returns:
        List of Tool instances scoped to the harness
    """
    tools = [
        ScopedDocumentReaderTool(harness),
        ScopedDocumentListTool(harness),
        ScopedDocumentCreateTool(harness),
        ScopedSourceEntityTool(harness),
        ScopedExternalFetchTool(harness),
        ScopedProjectInfoTool(harness),
    ]

    # Only add search tool if project-scoped
    if harness.context.project_id is not None:
        tools.append(ScopedDocumentSearchTool(harness))

    return tools
