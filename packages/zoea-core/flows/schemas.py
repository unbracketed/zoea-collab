"""
Pydantic schemas for flows API.

These schemas serialize workflow specifications for API responses.
"""


from pydantic import BaseModel, ConfigDict, Field


class InputSpecOut(BaseModel):
    """Serialized input specification for API response."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Input parameter name")
    type: str = Field(..., description="Input type (str, int, PositiveInt, etc.)")
    description: str = Field(default="", description="Human-readable description")
    required: bool = Field(default=True, description="Whether input is required")
    default_value: str | None = Field(
        default=None, description="Default value if not provided"
    )


class OutputSpecOut(BaseModel):
    """Serialized output specification for API response."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Output name (may contain template variables)")
    type: str = Field(..., description="Output type (MarkdownDocument, D2Diagram, etc.)")
    target: str | None = Field(
        default=None, description="Target folder path (may contain template variables)"
    )


class WorkflowOut(BaseModel):
    """Full workflow information for listing endpoint."""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(..., description="Workflow identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(default="", description="Workflow description")
    inputs: list[InputSpecOut] = Field(
        default_factory=list, description="List of input specifications"
    )
    outputs: list[OutputSpecOut] = Field(
        default_factory=list, description="List of output specifications"
    )


class WorkflowListResponse(BaseModel):
    """Response schema for workflow list endpoint."""

    workflows: list[WorkflowOut] = Field(..., description="List of available workflows")
    total: int = Field(..., description="Total number of workflows")


class ExecutionRunRequest(BaseModel):
    """Request schema for workflow execution endpoint."""

    model_config = ConfigDict(extra="allow")

    inputs: dict = Field(
        default_factory=dict,
        description="Dynamic inputs dictionary matching workflow InputSpec",
    )
    project_id: int | None = Field(
        default=None, description="Project ID (uses default if not provided)"
    )
    workspace_id: int | None = Field(
        default=None, description="Workspace ID (uses project default if not provided)"
    )
    background: bool = Field(
        default=False,
        description="If true, execute in background and return immediately with pending status",
    )


class ExecutionOutputResult(BaseModel):
    """Schema for individual output result in workflow response."""

    model_config = ConfigDict(from_attributes=True)

    type: str = Field(..., description="Output type (MarkdownDocument, D2Diagram, etc.)")
    id: int | str | None = Field(default=None, description="ID of created resource")
    name: str | None = Field(default=None, description="Name of created resource")
    folder: str | None = Field(default=None, description="Target folder path")
    error: str | None = Field(default=None, description="Error message if output failed")
    content: str | None = Field(
        default=None, description="Content preview for unsupported types"
    )


class ExecutionRunResponse(BaseModel):
    """Response schema for workflow execution endpoint."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(
        ..., description="Execution status: pending, running, completed, failed, cancelled"
    )
    run_id: str = Field(..., description="Unique identifier for this workflow run")
    workflow: str = Field(..., description="Workflow slug that was executed")
    outputs: dict[str, ExecutionOutputResult] | None = Field(
        default=None, description="Output results keyed by output name (null if pending/running)"
    )
    error: str | None = Field(
        default=None, description="Error message if execution failed"
    )
    task_id: str | None = Field(
        default=None, description="Background task ID (if background=true)"
    )


class ExecutionValidationError(BaseModel):
    """Schema for input validation error details."""

    field: str = Field(..., description="Input field name that failed validation")
    message: str = Field(..., description="Validation error message")


class ExecutionRunErrorResponse(BaseModel):
    """Error response schema for workflow execution failures."""

    status: str = Field(default="failed", description="Execution status")
    error: str = Field(..., description="Error message")
    validation_errors: list[ExecutionValidationError] | None = Field(
        default=None, description="List of input validation errors (for 400 responses)"
    )


# ============================================================================
# Execution Run History Schemas
# ============================================================================


class ExecutionRunListItem(BaseModel):
    """Schema for workflow run in list view."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str = Field(..., description="Unique identifier for this workflow run")
    workflow_slug: str = Field(..., description="Workflow slug")
    workflow_name: str = Field(..., description="Human-readable workflow name")
    status: str = Field(..., description="Execution status")
    created_at: str = Field(..., description="When the run was created (ISO format)")
    started_at: str | None = Field(default=None, description="When execution started")
    completed_at: str | None = Field(default=None, description="When execution completed")
    duration_seconds: float | None = Field(default=None, description="Execution duration")
    created_by_username: str | None = Field(default=None, description="Username who initiated")


class ExecutionRunDetail(ExecutionRunListItem):
    """Full workflow run details for single-item view."""

    inputs: dict = Field(default_factory=dict, description="Input parameters used")
    outputs: dict | None = Field(default=None, description="Output results")
    error: str | None = Field(default=None, description="Error message if failed")
    provider_model: str | None = Field(default=None, description="AI provider/model used")
    task_id: str | None = Field(default=None, description="Background task ID")
    project_id: int = Field(..., description="Project ID")
    workspace_id: int = Field(..., description="Workspace ID")


class ExecutionRunListResponse(BaseModel):
    """Response for workflow runs list endpoint."""

    runs: list[ExecutionRunListItem] = Field(..., description="List of workflow runs")
    total: int = Field(..., description="Total number of runs matching filters")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=20, description="Items per page")
