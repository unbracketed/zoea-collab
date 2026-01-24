"""
Pydantic schemas for Document RAG API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from ninja import Schema


class CreateRAGSessionRequest(Schema):
    """Request to create a new RAG session."""

    context_type: Literal["single", "folder", "collection"]
    context_id: int
    project_id: int
    reuse_existing: bool = True  # If True, reuse active session for same context


class RAGSessionResponse(Schema):
    """Response for session creation/retrieval."""

    session_id: str
    status: str
    document_count: int
    context_type: str
    context_display: str
    created_at: datetime


class RAGSessionDetailResponse(Schema):
    """Detailed session response including messages."""

    session_id: str
    status: str
    document_count: int
    context_type: str
    context_display: str
    created_at: datetime
    messages: list[RAGMessageResponse]


class RAGChatRequest(Schema):
    """Request to send a message to the RAG agent."""

    message: str
    include_sources: bool = True


class DocumentSourceRef(Schema):
    """Reference to a source document."""

    document_id: int | None = None
    document_name: str | None = None
    document_type: str | None = None
    relevance_score: float | None = None
    excerpt: str | None = None
    uri: str | None = None
    title: str | None = None


class RAGChatResponse(Schema):
    """Response from the RAG agent."""

    message_id: int
    response: str
    sources: list[DocumentSourceRef]
    thinking_steps: list[str] | None = None


class RAGMessageResponse(Schema):
    """A message in the RAG session."""

    id: int
    role: str
    content: str
    created_at: datetime
    sources: list[DocumentSourceRef] = []
    thinking_steps: list[str] = []


# Resolve forward reference
RAGSessionDetailResponse.model_rebuild()
