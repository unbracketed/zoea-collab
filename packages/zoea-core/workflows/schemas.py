"""Pydantic schemas for workflow API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ArtifactItem(BaseModel):
    """Schema for a single artifact item."""

    id: int = Field(..., description="Artifact item ID")
    source_channel: str = Field(..., description="Source channel (code, document, etc.)")
    source_metadata: dict = Field(default_factory=dict, description="Artifact metadata")
    preview: Optional[dict] = Field(None, description="Preview data for rendering")
    is_pinned: bool = Field(False, description="Whether the artifact is pinned")
    created_at: datetime = Field(..., description="When the artifact was created")

    class Config:
        from_attributes = True


class ExecutionRunArtifactListResponse(BaseModel):
    """Response schema for execution run artifacts endpoint."""

    items: List[ArtifactItem] = Field(..., description="List of artifact items")
    total: int = Field(..., description="Total number of artifacts")
    collection_id: Optional[int] = Field(None, description="ID of the artifact collection")
    workflow_slug: str = Field(..., description="Slug of the workflow")
    run_id: str = Field(..., description="UUID of the run")
    status: str = Field(..., description="Status of the run")
