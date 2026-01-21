"""
Pydantic schemas for project API.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectItem(BaseModel):
    """Schema for a single project in list view."""

    id: int = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    slug: str = Field(..., description="URL-friendly slug")
    working_directory: str = Field(..., description="Working directory path")
    worktree_directory: Optional[str] = Field(None, description="Worktree directory path")
    description: str = Field(..., description="Project description")
    color_theme: Optional[str] = Field(None, description="Color theme name")
    color: str = Field(..., description="Hex color for the project theme")
    avatar_url: Optional[str] = Field(None, description="URL to project avatar image")
    use_primary_header: bool = Field(False, description="Use theme primary color for app header")
    canonical_email: str = Field(..., description="Auto-generated canonical email address")
    email_alias: Optional[str] = Field(None, description="User-configurable email alias (local part only)")
    alias_email: Optional[str] = Field(None, description="Full alias email address if alias is set")
    created_at: datetime = Field(..., description="When the project was created")
    updated_at: datetime = Field(..., description="When the project was last updated")

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Response schema for project list endpoint."""

    projects: List[ProjectItem] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")


class ProjectDetailResponse(BaseModel):
    """Response schema for project detail endpoint."""

    id: int = Field(..., description="Project ID")
    name: str = Field(..., description="Project name")
    slug: str = Field(..., description="URL-friendly slug")
    working_directory: str = Field(..., description="Working directory path")
    worktree_directory: Optional[str] = Field(None, description="Worktree directory path")
    description: str = Field(..., description="Project description")
    color_theme: Optional[str] = Field(None, description="Color theme name")
    color: str = Field(..., description="Hex color for the project theme")
    avatar_url: Optional[str] = Field(None, description="URL to project avatar image")
    use_primary_header: bool = Field(False, description="Use theme primary color for app header")
    canonical_email: str = Field(..., description="Auto-generated canonical email address")
    email_alias: Optional[str] = Field(None, description="User-configurable email alias (local part only)")
    alias_email: Optional[str] = Field(None, description="Full alias email address if alias is set")
    created_at: datetime = Field(..., description="When the project was created")
    updated_at: datetime = Field(..., description="When the project was last updated")


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a project."""

    name: str = Field(..., description="Project name")
    description: Optional[str] = Field("", description="Project description")
    color_theme: Optional[str] = Field(None, description="Color theme name")
    use_primary_header: Optional[bool] = Field(False, description="Use theme primary color for app header")


class ProjectUpdateRequest(BaseModel):
    """Request schema for updating a project."""

    name: Optional[str] = Field(None, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    color_theme: Optional[str] = Field(None, description="Color theme name")
    use_primary_header: Optional[bool] = Field(None, description="Use theme primary color for app header")
    email_alias: Optional[str] = Field(None, description="Email alias (local part only, set to empty string to clear)")


class AvatarUploadResponse(BaseModel):
    """Response schema for avatar upload."""

    avatar_url: str = Field(..., description="URL to the uploaded avatar")
