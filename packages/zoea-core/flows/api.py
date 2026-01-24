"""
Django Ninja API for flows endpoints.

Provides endpoints for listing and interacting with available workflows.
"""

import logging
from pathlib import Path
from typing import Any

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import (
    aget_user_default_project,
    aget_user_organization,
)
from workflows.config import load_workflow_config
from workflows.exceptions import WorkflowError
from workflows.registry import WorkflowRegistry
from workflows.runner import WorkflowRunner

from .schemas import (
    InputSpecOut,
    OutputSpecOut,
    WorkflowOut,
    ExecutionOutputResult,
    ExecutionRunDetail,
    ExecutionRunErrorResponse,
    ExecutionRunListItem,
    ExecutionRunListResponse,
    ExecutionRunRequest,
    ExecutionRunResponse,
    ExecutionValidationError,
)

router = Router()
logger = logging.getLogger(__name__)


def _ensure_workflows_discovered() -> None:
    """
    Ensure built-in workflows are discovered and registered.

    This function is idempotent - calling it multiple times will not
    re-register workflows that are already registered.
    """
    registry = WorkflowRegistry.get_instance()
    if not registry.list_workflows():
        # Discover built-in workflows if registry is empty
        workflows_path = Path(__file__).parent.parent / "workflows"
        registry.discover_builtins(workflows_path)
        logger.debug(f"Discovered workflows from {workflows_path}")


def _convert_workflow_to_out(slug: str, workflow_data: dict) -> WorkflowOut:
    """
    Convert internal workflow data to API response format.

    Args:
        slug: Workflow identifier
        workflow_data: Internal workflow data with config_path and flow_builder

    Returns:
        WorkflowOut instance for API response
    """
    config_path = workflow_data.get("config_path")
    if not config_path:
        # Return minimal workflow info if no config
        return WorkflowOut(
            slug=slug,
            name=slug.replace("-", " ").replace("_", " ").title(),
            description="",
            inputs=[],
            outputs=[],
        )

    try:
        spec = load_workflow_config(config_path)
    except Exception as e:
        logger.warning(f"Failed to load config for workflow '{slug}': {e}")
        return WorkflowOut(
            slug=slug,
            name=slug.replace("-", " ").replace("_", " ").title(),
            description="",
            inputs=[],
            outputs=[],
        )

    # Convert InputSpec to InputSpecOut
    inputs = [
        InputSpecOut(
            name=inp.name,
            type=inp.type,
            description=inp.description,
            required=inp.required,
            default_value=str(inp.value) if inp.value is not None else None,
        )
        for inp in spec.inputs
    ]

    # Convert OutputSpec to OutputSpecOut
    outputs = [
        OutputSpecOut(
            name=out.name,
            type=out.type,
            target=out.target,
        )
        for out in spec.outputs
    ]

    return WorkflowOut(
        slug=spec.slug,
        name=spec.name or slug.replace("-", " ").replace("_", " ").title(),
        description=spec.description,
        inputs=inputs,
        outputs=outputs,
    )


@router.get("/workflows", response=list[WorkflowOut])
def list_workflows(request) -> list[WorkflowOut]:
    """
    List all available workflows.

    Returns a list of workflow definitions including their inputs, outputs,
    and metadata. This endpoint discovers and loads workflow configurations
    from the built-in workflows directory.

    Returns:
        List of WorkflowOut with workflow metadata, inputs, and outputs
    """
    _ensure_workflows_discovered()

    registry = WorkflowRegistry.get_instance()
    workflows_data = registry.list_workflows()

    workflows = []
    for slug, data in workflows_data.items():
        workflow_out = _convert_workflow_to_out(slug, data)
        workflows.append(workflow_out)

    logger.info(f"Listed {len(workflows)} available workflows")
    return workflows


@router.get("/workflows/{slug}", response=WorkflowOut)
def get_workflow(request, slug: str) -> WorkflowOut:
    """
    Get a specific workflow by slug.

    Args:
        request: Django request object
        slug: Workflow identifier

    Returns:
        WorkflowOut with workflow metadata, inputs, and outputs

    Raises:
        HttpError: 404 if workflow not found
    """
    _ensure_workflows_discovered()

    registry = WorkflowRegistry.get_instance()
    workflow_data = registry.get(slug)

    if workflow_data is None:
        raise HttpError(404, f"Workflow '{slug}' not found")

    return _convert_workflow_to_out(slug, workflow_data)


@router.post(
    "/workflows/{slug}/run",
    response={
        200: ExecutionRunResponse,
        400: ExecutionRunErrorResponse,
        500: ExecutionRunErrorResponse,
    },
)
async def run_workflow(
    request,
    slug: str,
    payload: ExecutionRunRequest,
) -> ExecutionRunResponse:
    """
    Execute a workflow by slug.

    Validates inputs against the workflow's InputSpec, executes the workflow
    via WorkflowRunner, and returns structured output with results.

    Args:
        request: Django request object
        slug: Workflow identifier
        payload: Request body with inputs and optional project ID

    Returns:
        ExecutionRunResponse with execution status and outputs

    Raises:
        HttpError: 404 if workflow not found
        HttpError: 400 if input validation fails
        HttpError: 403 if user lacks organization access
        HttpError: 500 if execution error occurs
    """
    _ensure_workflows_discovered()

    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get workflow from registry
    registry = WorkflowRegistry.get_instance()
    workflow_data = registry.get(slug)

    if workflow_data is None:
        raise HttpError(404, f"Workflow '{slug}' not found")

    # Load workflow spec to validate inputs
    config_path = workflow_data.get("config_path")
    if not config_path:
        raise HttpError(500, f"Workflow '{slug}' has no configuration")

    try:
        spec = load_workflow_config(Path(config_path))
    except Exception as e:
        logger.error(f"Failed to load workflow config for '{slug}': {e}")
        raise HttpError(500, f"Failed to load workflow configuration: {e}")

    # Validate inputs against InputSpec
    validation_errors = _validate_workflow_inputs(spec, payload.inputs)
    if validation_errors:
        return 400, ExecutionRunErrorResponse(
            status="failed",
            error="Input validation failed",
            validation_errors=validation_errors,
        )

    # Get project context
    project = await _get_project_context(request.user, organization, payload.project_id)
    if not project:
        raise HttpError(400, "No project available. Please create a project first.")

    # Execute workflow - background or synchronous
    if payload.background:
        # Background execution: queue task and return immediately
        try:
            from workflows.tasks import create_and_queue_workflow_run

            run = await sync_to_async(create_and_queue_workflow_run)(
                workflow_slug=slug,
                inputs=payload.inputs,
                organization=organization,
                project=project,
                user=request.user,
            )

            return ExecutionRunResponse(
                status="pending",
                run_id=str(run.run_id),
                workflow=slug,
                outputs=None,
                task_id=run.task_id,
            )

        except Exception as e:
            logger.exception(f"Failed to queue background workflow '{slug}': {e}")
            return 500, ExecutionRunErrorResponse(
                status="failed",
                error=f"Failed to queue workflow: {str(e)}",
            )

    else:
        # Synchronous execution (default for backwards compat)
        try:
            runner = WorkflowRunner(organization, project, request.user)
            result = await runner.run(slug, payload.inputs)

            # Convert outputs to schema format
            outputs = {}
            for output_name, output_data in result.get("outputs", {}).items():
                outputs[output_name] = ExecutionOutputResult(**output_data)

            return ExecutionRunResponse(
                status="completed",
                run_id=result.get("run_id", ""),
                workflow=result.get("workflow", slug),
                outputs=outputs,
            )

        except WorkflowError as e:
            logger.error(f"Workflow execution error for '{slug}': {e}")
            return 500, ExecutionRunErrorResponse(
                status="failed",
                error=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error executing workflow '{slug}': {e}")
            return 500, ExecutionRunErrorResponse(
                status="failed",
                error=f"Workflow execution failed: {str(e)}",
            )


def _validate_workflow_inputs(spec, inputs: dict[str, Any]) -> list[ExecutionValidationError]:
    """
    Validate inputs against workflow's InputSpec.

    Args:
        spec: WorkflowSpec with input definitions
        inputs: User-provided input values

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for input_spec in spec.inputs:
        value = inputs.get(input_spec.name)

        try:
            input_spec.validate_value(value)
        except ValueError as e:
            errors.append(
                ExecutionValidationError(
                    field=input_spec.name,
                    message=str(e),
                )
            )

    return errors


async def _get_project_context(user, organization, project_id: int | None):
    """
    Get project context for workflow execution.

    Args:
        user: Django User instance
        organization: Organization instance
        project_id: Optional explicit project ID

    Returns:
        Project instance or None
    """
    from projects.models import Project

    if project_id:
        # Fetch explicit project, verify it belongs to organization
        @sync_to_async
        def _get_project():
            try:
                return Project.objects.get(id=project_id, organization=organization)
            except Project.DoesNotExist:
                return None

        return await _get_project()
    else:
        # Use default project
        return await aget_user_default_project(user)


# ============================================================================
# Execution Runs Endpoints
# ============================================================================


@router.get("/runs", response=ExecutionRunListResponse)
async def list_workflow_runs(
    request,
    status: str | None = None,
    workflow_slug: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> ExecutionRunListResponse:
    """
    List workflow runs for the current user's organization.

    Args:
        request: Django request object
        status: Filter by status (pending, running, completed, failed, cancelled)
        workflow_slug: Filter by workflow slug
        page: Page number (1-indexed)
        per_page: Items per page (max 100)

    Returns:
        ExecutionRunListResponse with paginated list of runs
    """
    from execution.models import ExecutionRun

    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Clamp pagination values
    per_page = min(max(per_page, 1), 100)
    page = max(page, 1)
    offset = (page - 1) * per_page

    @sync_to_async
    def _fetch_runs():
        queryset = ExecutionRun.objects.filter(
            organization=organization,
            workflow_slug__isnull=False,
        )

        # Apply filters
        if status:
            queryset = queryset.filter(status=status)
        if workflow_slug:
            queryset = queryset.filter(workflow_slug=workflow_slug)

        # Get total count
        total = queryset.count()

        # Fetch paginated results
        runs_qs = queryset.select_related("created_by").order_by("-created_at")[
            offset : offset + per_page
        ]

        runs = []
        for run in runs_qs:
            # Get workflow name from registry
            workflow_data = WorkflowRegistry.get_instance().get(run.workflow_slug)
            if workflow_data and workflow_data.get("config_path"):
                try:
                    spec = load_workflow_config(workflow_data["config_path"])
                    workflow_name = spec.name or run.workflow_slug.replace("_", " ").title()
                except Exception:
                    workflow_name = run.workflow_slug.replace("_", " ").title()
            else:
                workflow_name = run.workflow_slug.replace("_", " ").title()

            runs.append(
                ExecutionRunListItem(
                    run_id=str(run.run_id),
                    workflow_slug=run.workflow_slug,
                    workflow_name=workflow_name,
                    status=run.status,
                    created_at=run.created_at.isoformat(),
                    started_at=run.started_at.isoformat() if run.started_at else None,
                    completed_at=run.completed_at.isoformat() if run.completed_at else None,
                    duration_seconds=run.duration_seconds,
                    created_by_username=run.created_by.username if run.created_by else None,
                )
            )

        return runs, total

    _ensure_workflows_discovered()
    runs, total = await _fetch_runs()

    return ExecutionRunListResponse(
        runs=runs,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/runs/{run_id}", response={200: ExecutionRunDetail, 404: ExecutionRunErrorResponse})
async def get_workflow_run(request, run_id: str):
    """
    Get details for a specific workflow run.

    Args:
        request: Django request object
        run_id: Workflow run ID

    Returns:
        ExecutionRunDetail with full run information
    """
    from execution.models import ExecutionRun

    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _fetch_run():
        try:
            return ExecutionRun.objects.select_related("created_by", "project").get(
                run_id=run_id,
                organization=organization,
                workflow_slug__isnull=False,
            )
        except ExecutionRun.DoesNotExist:
            return None

    _ensure_workflows_discovered()
    run = await _fetch_run()

    if not run:
        return 404, ExecutionRunErrorResponse(error=f"Run not found: {run_id}")

    # Get workflow name from registry
    workflow_data = WorkflowRegistry.get_instance().get(run.workflow_slug)
    if workflow_data and workflow_data.get("config_path"):
        try:
            spec = load_workflow_config(workflow_data["config_path"])
            workflow_name = spec.name or run.workflow_slug.replace("_", " ").title()
        except Exception:
            workflow_name = run.workflow_slug.replace("_", " ").title()
    else:
        workflow_name = run.workflow_slug.replace("_", " ").title()

    return ExecutionRunDetail(
        run_id=str(run.run_id),
        workflow_slug=run.workflow_slug,
        workflow_name=workflow_name,
        status=run.status,
        created_at=run.created_at.isoformat(),
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        duration_seconds=run.duration_seconds,
        created_by_username=run.created_by.username if run.created_by else None,
        inputs=run.inputs,
        outputs=run.outputs,
        error=run.error,
        provider_model=run.provider_model,
        task_id=run.task_id,
        project_id=run.project.id if run.project else None,
    )
