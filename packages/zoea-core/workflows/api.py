"""Django Ninja API for workflow endpoints."""

import logging
from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from .models import WorkflowRun
from .schemas import ArtifactItem, WorkflowRunArtifactListResponse

router = Router()
logger = logging.getLogger(__name__)


@router.get("/runs/{run_id}/artifacts", response=WorkflowRunArtifactListResponse)
async def get_workflow_run_artifacts(request, run_id: str):
    """
    Get artifacts for a workflow run.

    Args:
        request: Django request object
        run_id: UUID of the workflow run

    Returns:
        List of artifact items for the workflow run

    Raises:
        HttpError: If workflow run not found or user doesn't have access
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _get_artifacts():
        try:
            workflow_run = WorkflowRun.objects.get(
                run_id=run_id,
                organization=organization,
            )
        except WorkflowRun.DoesNotExist:
            raise HttpError(404, f"Workflow run {run_id} not found or access denied")

        # Return empty list if no artifacts collection
        if not workflow_run.artifacts_id:
            return {
                'items': [],
                'total': 0,
                'collection_id': None,
                'workflow_slug': workflow_run.workflow_slug,
                'run_id': str(workflow_run.run_id),
                'status': workflow_run.status,
            }

        # Get artifact items
        items = workflow_run.artifacts.items.order_by('position')
        artifact_list = []
        for item in items:
            artifact_list.append({
                'id': item.id,
                'source_channel': item.source_channel,
                'source_metadata': item.source_metadata or {},
                'preview': item.preview,
                'is_pinned': item.is_pinned,
                'created_at': item.created_at,
            })

        return {
            'items': artifact_list,
            'total': len(artifact_list),
            'collection_id': workflow_run.artifacts_id,
            'workflow_slug': workflow_run.workflow_slug,
            'run_id': str(workflow_run.run_id),
            'status': workflow_run.status,
        }

    artifacts_data = await _get_artifacts()
    return WorkflowRunArtifactListResponse(**artifacts_data)
