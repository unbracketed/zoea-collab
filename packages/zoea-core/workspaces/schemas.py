"""
Pydantic schemas for workspace API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WorkspaceItem(BaseModel):
    """Schema for a single workspace in list view."""

    id: int = Field(..., description="Workspace ID")
    name: str = Field(..., description="Workspace name")
    slug: str = Field(..., description="URL-friendly slug")
    description: str = Field(..., description="Workspace description")
    project_id: int = Field(..., description="ID of the project this workspace belongs to")
    project_name: str = Field(..., description="Name of the project")
    parent_id: Optional[int] = Field(None, description="ID of parent workspace (null for root)")
    level: int = Field(..., description="Depth level in the tree (0 for root)")
    full_path: str = Field(..., description="Full path from root to this workspace")
    canonical_email: str = Field(..., description="Auto-generated canonical email address")
    email_alias: Optional[str] = Field(None, description="User-configurable email alias (local part only)")
    alias_email: Optional[str] = Field(None, description="Full alias email address if alias is set")
    created_at: datetime = Field(..., description="When the workspace was created")
    updated_at: datetime = Field(..., description="When the workspace was last updated")

    class Config:
        from_attributes = True


class WorkspaceListResponse(BaseModel):
    """Response schema for workspace list endpoint."""

    workspaces: List[WorkspaceItem] = Field(..., description="List of workspaces")
    total: int = Field(..., description="Total number of workspaces")


class WorkspaceDetailResponse(BaseModel):
    """Response schema for workspace detail endpoint."""

    id: int = Field(..., description="Workspace ID")
    name: str = Field(..., description="Workspace name")
    slug: str = Field(..., description="URL-friendly slug")
    description: str = Field(..., description="Workspace description")
    project_id: int = Field(..., description="ID of the project this workspace belongs to")
    project_name: str = Field(..., description="Name of the project")
    parent_id: Optional[int] = Field(None, description="ID of parent workspace (null for root)")
    level: int = Field(..., description="Depth level in the tree (0 for root)")
    full_path: str = Field(..., description="Full path from root to this workspace")
    canonical_email: str = Field(..., description="Auto-generated canonical email address")
    email_alias: Optional[str] = Field(None, description="User-configurable email alias (local part only)")
    alias_email: Optional[str] = Field(None, description="Full alias email address if alias is set")
    created_at: datetime = Field(..., description="When the workspace was created")
    updated_at: datetime = Field(..., description="When the workspace was last updated")


class WorkspaceUpdateRequest(BaseModel):
    """Request schema for updating a workspace."""

    name: Optional[str] = Field(None, description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")
    email_alias: Optional[str] = Field(None, description="Email alias (local part only, set to empty string to clear)")
