"""
Pydantic schemas for events API.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from .models import EventType


class EventTriggerCreate(BaseModel):
    """Schema for creating an event trigger."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    event_type: str = Field(..., description="Event type from EventType choices")
    skills: list[str] = Field(..., min_length=1, description="List of skill names to execute")
    project_id: int | None = Field(
        default=None, description="Optional project scope (None = org-wide)"
    )
    is_enabled: bool = Field(default=True)
    run_async: bool = Field(default=True)
    filters: dict = Field(default_factory=dict)
    agent_config: dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Extract Lead Data",
                "description": "Extract structured lead data from incoming emails",
                "event_type": "email_received",
                "skills": ["extract-lead-data", "crm-sync"],
                "project_id": 1,
                "is_enabled": True,
                "run_async": True,
                "filters": {},
                "agent_config": {"max_steps": 10},
            }
        }


class EventTriggerUpdate(BaseModel):
    """Schema for updating an event trigger."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    skills: list[str] | None = Field(default=None, min_length=1)
    is_enabled: bool | None = None
    run_async: bool | None = None
    filters: dict | None = None
    agent_config: dict | None = None


class EventTriggerResponse(BaseModel):
    """Response schema for an event trigger."""

    id: int
    name: str
    description: str
    event_type: str
    skills: list[str]
    skill_count: int
    project_id: int | None
    project_name: str | None
    is_enabled: bool
    run_async: bool
    filters: dict
    agent_config: dict
    created_at: datetime
    updated_at: datetime
    created_by_id: int | None

    class Config:
        from_attributes = True


class EventTriggerRunResponse(BaseModel):
    """Response schema for a trigger run."""

    id: int
    run_id: str
    trigger_id: int
    trigger_name: str
    source_type: str
    source_id: int
    status: str
    inputs: dict
    outputs: dict | None
    error: str | None
    telemetry: dict | None
    duration_seconds: float | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class EventTypeInfo(BaseModel):
    """Information about an event type."""

    value: str
    label: str


class EventTypesResponse(BaseModel):
    """Response with available event types."""

    event_types: list[EventTypeInfo]


class ManualDispatchRequest(BaseModel):
    """Schema for manually dispatching a trigger with document selection."""

    document_ids: list[int] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of document IDs to process",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "document_ids": [1, 2, 3],
            }
        }
