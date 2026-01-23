"""
Background tasks for workflow execution via Django-Q2.

This module contains task functions that are executed asynchronously
by the Django-Q2 worker process.

Usage:
    from workflows.tasks import create_and_queue_workflow_run

    run = create_and_queue_workflow_run(
        workflow_slug='summarize_content',
        inputs={'document_id': 123},
        organization=org,
        project=project,
        workspace=workspace,
        user=user,
    )
    # Returns ExecutionRun instance with run.run_id and run.task_id
"""

import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def execute_workflow_background(
    run_id: str,
    workflow_slug: str,
    inputs: dict,
    org_id: int,
    project_id: int,
    workspace_id: int,
    user_id: int,
) -> dict:
    """
    Background task to execute a workflow.

    This function is called by Django-Q2 workers. It loads the necessary
    context objects, executes the workflow synchronously within the worker,
    and updates the ExecutionRun record with results.

    Args:
        run_id: Unique identifier for this workflow run
        workflow_slug: Slug of the workflow to execute
        inputs: Input parameters for the workflow
        org_id: Organization ID for context
        project_id: Project ID for context
        workspace_id: Workspace ID for context
        user_id: User ID who initiated the run

    Returns:
        dict with run_id and final status

    Raises:
        Exception: Re-raised from workflow execution so Django-Q marks task as failed
    """
    import asyncio

    from django.contrib.auth import get_user_model

    from organizations.models import Organization
    from projects.models import Project
    from workspaces.models import Workspace
    from execution.models import ExecutionRun
    from workflows.runner import WorkflowRunner

    logger.info(f"Starting background execution of workflow '{workflow_slug}' run {run_id}")

    # Load context objects
    try:
        org = Organization.objects.get(id=org_id)
        project = Project.objects.get(id=project_id)
        workspace = Workspace.objects.get(id=workspace_id)
        user = get_user_model().objects.get(id=user_id)
    except Exception as e:
        logger.error(f"Failed to load context for run {run_id}: {e}")
        raise

    # Get run record
    try:
        run = ExecutionRun.objects.get(run_id=run_id)
    except ExecutionRun.DoesNotExist:
        logger.error(f"ExecutionRun not found: {run_id}")
        raise

    # Update run status to running
    run.status = ExecutionRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    logger.info(f"Run {run_id} status updated to 'running'")

    try:
        # Ensure workflows are discovered (worker is a separate process)
        from pathlib import Path
        from workflows.registry import WorkflowRegistry
        registry = WorkflowRegistry.get_instance()
        if not registry.list_workflows():
            workflows_path = Path(__file__).parent
            registry.discover_builtins(workflows_path)
            logger.info(f"Discovered workflows: {list(registry.list_workflows().keys())}")

        # Execute workflow synchronously within the task
        runner = WorkflowRunner(org, project, workspace, user)
        result = asyncio.run(runner.run(workflow_slug, inputs))

        # Update with results
        run.status = ExecutionRun.Status.COMPLETED
        run.outputs = result.get("outputs", {})
        run.completed_at = timezone.now()

        # Track provider/model if available from settings
        # TODO: Enhance WorkflowRunner to return actual model used
        run.provider_model = f"{settings.DEFAULT_LLM_PROVIDER}/{settings.DEFAULT_LLM_MODEL}"

        run.save(update_fields=[
            "status", "outputs", "completed_at", "provider_model", "updated_at"
        ])

        logger.info(f"Run {run_id} completed successfully")
        return {"run_id": run_id, "status": "completed"}

    except Exception as e:
        logger.error(f"Run {run_id} failed: {e}", exc_info=True)

        run.status = ExecutionRun.Status.FAILED
        run.error = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at", "updated_at"])

        raise  # Re-raise so Django-Q marks task as failed


def create_and_queue_workflow_run(
    workflow_slug: str,
    inputs: dict,
    organization,
    project,
    workspace,
    user,
    timeout: int = 600,
):
    """
    Create an ExecutionRun record and queue it for background execution.

    This is the main entry point for background workflow execution from API endpoints.

    Args:
        workflow_slug: Slug of the workflow to execute
        inputs: Input parameters for the workflow
        organization: Organization instance
        project: Project instance
        workspace: Workspace instance
        user: User instance who initiated the run
        timeout: Task timeout in seconds (default 10 minutes)

    Returns:
        ExecutionRun instance with task_id set
    """
    from django_q.tasks import async_task

    from execution.models import ExecutionRun

    # Create the run record
    run = ExecutionRun.objects.create(
        organization=organization,
        workflow_slug=workflow_slug,
        graph_id=workflow_slug,
        trigger_type="workflow",
        status=ExecutionRun.Status.PENDING,
        inputs=inputs,
        created_by=user,
        project=project,
        workspace=workspace,
    )

    logger.info(f"Created ExecutionRun {run.run_id} for workflow '{workflow_slug}'")

    # Queue the background task
    task_id = async_task(
        "workflows.tasks.execute_workflow_background",
        str(run.run_id),
        workflow_slug,
        inputs,
        organization.id,
        project.id,
        workspace.id,
        user.id,
        task_name=f"workflow-{run.run_id}",
        timeout=timeout,
    )

    # Store task ID on the run record
    run.task_id = task_id
    run.save(update_fields=["task_id"])

    logger.info(f"Queued background task {task_id} for run {run.run_id}")

    return run


def get_workflow_run_status(run_id: str) -> dict:
    """
    Get the current status of a workflow run.

    Args:
        run_id: The workflow run ID

    Returns:
        dict with status info
    """
    from execution.models import ExecutionRun

    try:
        run = ExecutionRun.objects.get(run_id=run_id)
        return {
            "run_id": str(run.run_id),
            "workflow_slug": run.workflow_slug,
            "status": run.status,
            "inputs": run.inputs,
            "outputs": run.outputs,
            "error": run.error,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "provider_model": run.provider_model,
        }
    except ExecutionRun.DoesNotExist:
        return {"error": f"Run not found: {run_id}"}
