"""Pydantic schemas for clipboard API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import ClipboardDirection, ClipboardSourceChannel


class ClipboardSchema(BaseModel):
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


class ClipboardWithMetadata(ClipboardSchema):
    metadata: dict[str, Any]
    sequence_head: int
    sequence_tail: int


class ClipboardListResponse(BaseModel):
    clipboards: list[ClipboardSchema]
    total: int


class ClipboardDetailResponse(BaseModel):
    clipboard: ClipboardWithMetadata
    items: list[ClipboardItemSchema] | None = None


class ClipboardCreateRequest(BaseModel):
    workspace_id: int = Field(..., description="Workspace that will own the clipboard")
    name: str | None = None
    description: str | None = None
    activate: bool = True


class ClipboardActivateResponse(BaseModel):
    clipboard: ClipboardWithMetadata


class ClipboardItemSchema(BaseModel):
    id: int
    clipboard_id: int
    position: int
    direction_added: ClipboardDirection
    is_pinned: bool
    content_type: str | None = None
    object_id: str | None = None
    virtual_node_id: int | None = None
    source_channel: ClipboardSourceChannel
    source_metadata: dict[str, Any]
    preview: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClipboardItemListResponse(BaseModel):
    items: list[ClipboardItemSchema]
    total: int


class ClipboardItemCreateRequest(BaseModel):
    direction: ClipboardDirection = ClipboardDirection.RIGHT
    content_type: str | None = Field(
        None,
        description="Django content type in 'app_label.model' format",
    )
    object_id: str | int | None = None
    virtual_node_id: int | None = None
    source_channel: ClipboardSourceChannel = ClipboardSourceChannel.UNKNOWN
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] | None = Field(
        None,
        description="Custom preview data for the clipboard item",
    )


class ClipboardItemOperationResponse(BaseModel):
    item: ClipboardItemSchema


class ClipboardItemReorderEntry(BaseModel):
    item_id: int
    position: int


class ClipboardItemReorderRequest(BaseModel):
    items: list[ClipboardItemReorderEntry]


class ClipboardExportResponse(BaseModel):
    """Response schema for clipboard export endpoint."""

    format: str = Field(..., description="Export format (e.g., 'markdown')")
    content: str = Field(..., description="Exported content")
    item_count: int = Field(..., description="Number of items included in export")


class ClipboardSaveAsDocumentRequest(BaseModel):
    """Request schema for saving a notepad as a shared document."""

    name: str | None = Field(None, description="Name for the created document")
    description: str | None = Field(None, description="Optional document description")
    folder_id: int | None = Field(
        None, description="Optional folder ID in the same workspace"
    )


class ClipboardSaveAsDocumentResponse(BaseModel):
    """Response schema for save-as-document endpoint."""

    document_id: int = Field(..., description="Created document ID")
    document_name: str = Field(..., description="Created document name")


class ClipboardNotepadDraftUpdateRequest(BaseModel):
    """Update payload for a clipboard's notepad draft."""

    content: dict[str, Any] | None = Field(
        None,
        description="Yoopta JSON content dict (null to clear draft)",
    )


class ClipboardNotepadDraftResponse(BaseModel):
    """Response schema for notepad draft endpoints."""

    content: dict[str, Any] | None = Field(
        None,
        description="Current Yoopta JSON content dict (null when no draft)",
    )
