"""Pydantic schemas for notebook API.

These schemas mirror the clipboard schemas but use "notebook" terminology
to support the DocumentCollection-based notebook system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import CollectionItemDirection, CollectionItemSourceChannel


# =============================================================================
# Notebook Schemas
# =============================================================================


class NotebookSchema(BaseModel):
    """Base schema for notebook (DocumentCollection) responses."""

    id: int
    name: str
    description: str | None = None
    workspace_id: int
    owner_id: int
    is_active: bool
    is_recent: bool
    activated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotebookWithMetadata(NotebookSchema):
    """Notebook schema including metadata and sequence info."""

    metadata: dict[str, Any]
    sequence_head: int
    sequence_tail: int


class NotebookListResponse(BaseModel):
    """Response schema for listing notebooks."""

    notebooks: list[NotebookSchema]
    total: int


class NotebookDetailResponse(BaseModel):
    """Response schema for notebook detail with optional items."""

    notebook: NotebookWithMetadata
    items: list[NotebookItemSchema] | None = None


class NotebookCreateRequest(BaseModel):
    """Request schema for creating a new notebook."""

    workspace_id: int = Field(..., description="Workspace that will own the notebook")
    name: str | None = None
    description: str | None = None
    activate: bool = True


class NotebookActivateResponse(BaseModel):
    """Response schema for notebook activation."""

    notebook: NotebookWithMetadata


# =============================================================================
# Notebook Item Schemas
# =============================================================================


class NotebookItemSchema(BaseModel):
    """Schema for notebook item responses."""

    id: int
    notebook_id: int
    position: int
    direction_added: CollectionItemDirection
    is_pinned: bool
    content_type: str | None = None
    object_id: str | None = None
    virtual_node_id: int | None = None
    source_channel: CollectionItemSourceChannel
    source_metadata: dict[str, Any]
    preview: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotebookItemListResponse(BaseModel):
    """Response schema for listing notebook items."""

    items: list[NotebookItemSchema]
    total: int


class NotebookItemCreateRequest(BaseModel):
    """Request schema for creating a notebook item."""

    direction: CollectionItemDirection = CollectionItemDirection.RIGHT
    content_type: str | None = Field(
        None,
        description="Django content type in 'app_label.model' format",
    )
    object_id: str | int | None = None
    virtual_node_id: int | None = None
    source_channel: CollectionItemSourceChannel = CollectionItemSourceChannel.UNKNOWN
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] | None = Field(
        None,
        description="Custom preview data for the notebook item",
    )


class NotebookItemOperationResponse(BaseModel):
    """Response schema for item creation."""

    item: NotebookItemSchema


class NotebookItemReorderEntry(BaseModel):
    """Single item reorder entry."""

    item_id: int
    position: int


class NotebookItemReorderRequest(BaseModel):
    """Request schema for reordering items."""

    items: list[NotebookItemReorderEntry]


# =============================================================================
# Export Schemas
# =============================================================================


class NotebookExportResponse(BaseModel):
    """Response schema for notebook export endpoint."""

    format: str = Field(..., description="Export format (e.g., 'markdown')")
    content: str = Field(..., description="Exported content")
    item_count: int = Field(..., description="Number of items included in export")


# =============================================================================
# Save As Document Schemas
# =============================================================================


class NotebookSaveAsDocumentRequest(BaseModel):
    """Request schema for saving a notepad as a shared document."""

    name: str | None = Field(None, description="Name for the created document")
    description: str | None = Field(None, description="Optional document description")
    folder_id: int | None = Field(
        None, description="Optional folder ID in the same workspace"
    )


class NotebookSaveAsDocumentResponse(BaseModel):
    """Response schema for save-as-document endpoint."""

    document_id: int = Field(..., description="Created document ID")
    document_name: str = Field(..., description="Created document name")


# =============================================================================
# Notepad Draft Schemas
# =============================================================================


class NotebookNotepadDraftUpdateRequest(BaseModel):
    """Update payload for a notebook's notepad draft."""

    content: dict[str, Any] | None = Field(
        None,
        description="Yoopta JSON content dict (null to clear draft)",
    )


class NotebookNotepadDraftResponse(BaseModel):
    """Response schema for notepad draft endpoints."""

    content: dict[str, Any] | None = Field(
        None,
        description="Current Yoopta JSON content dict (null when no draft)",
    )
