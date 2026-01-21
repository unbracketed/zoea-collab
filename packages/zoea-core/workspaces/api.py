"""
Django Ninja API for workspace endpoints.
"""

from ninja import Router
from ninja.errors import HttpError
from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError as DjangoValidationError

from accounts.utils import aget_user_organization
from projects.email_utils import validate_email_alias
from .models import Workspace
from .schemas import WorkspaceListResponse, WorkspaceDetailResponse, WorkspaceUpdateRequest

router = Router()


@router.get("/workspaces", response=WorkspaceListResponse)
async def list_workspaces(request, project_id: int = None):
    """
    List all workspaces, optionally filtered by project.

    Args:
        request: Django request object
        project_id: Optional project ID to filter by

    Returns:
        List of workspaces with metadata
    """
    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get workspaces
    @sync_to_async
    def _get_workspaces():
        # Start with organization filter
        workspaces_query = Workspace.objects.filter(
            project__organization=organization
        ).select_related('project', 'parent', 'created_by')

        # Apply project filter if provided
        if project_id:
            workspaces_query = workspaces_query.filter(project_id=project_id)

        workspaces = workspaces_query.order_by('tree_id', 'lft')

        workspace_list = []
        for workspace in workspaces:
            workspace_list.append({
                'id': workspace.id,
                'name': workspace.name,
                'slug': workspace.slug,
                'description': workspace.description,
                'project_id': workspace.project_id,
                'project_name': workspace.project.name,
                'parent_id': workspace.parent_id if workspace.parent else None,
                'level': workspace.level,
                'full_path': workspace.get_full_path(),
                'canonical_email': workspace.canonical_email,
                'email_alias': workspace.email_alias,
                'alias_email': workspace.alias_email,
                'created_at': workspace.created_at,
                'updated_at': workspace.updated_at,
            })

        return workspace_list

    workspaces = await _get_workspaces()

    return WorkspaceListResponse(
        workspaces=workspaces,
        total=len(workspaces)
    )


@router.get("/workspaces/{workspace_id}", response=WorkspaceDetailResponse)
async def get_workspace(request, workspace_id: int):
    """
    Get a specific workspace with details.

    Args:
        request: Django request object
        workspace_id: ID of the workspace to fetch

    Returns:
        Workspace details

    Raises:
        HttpError: If workspace not found or user doesn't have access
    """
    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get workspace
    @sync_to_async
    def _get_workspace():
        try:
            workspace = Workspace.objects.select_related(
                'project', 'project__organization', 'parent', 'created_by'
            ).get(
                id=workspace_id,
                project__organization=organization
            )

            return {
                'id': workspace.id,
                'name': workspace.name,
                'slug': workspace.slug,
                'description': workspace.description,
                'project_id': workspace.project_id,
                'project_name': workspace.project.name,
                'parent_id': workspace.parent_id if workspace.parent else None,
                'level': workspace.level,
                'full_path': workspace.get_full_path(),
                'canonical_email': workspace.canonical_email,
                'email_alias': workspace.email_alias,
                'alias_email': workspace.alias_email,
                'created_at': workspace.created_at,
                'updated_at': workspace.updated_at,
            }
        except Workspace.DoesNotExist:
            raise HttpError(404, f"Workspace {workspace_id} not found or access denied")

    workspace_data = await _get_workspace()

    return WorkspaceDetailResponse(**workspace_data)


@router.patch("/workspaces/{workspace_id}", response=WorkspaceDetailResponse)
async def update_workspace(request, workspace_id: int, payload: WorkspaceUpdateRequest):
    """
    Update a workspace's settings.

    Args:
        request: Django request object
        workspace_id: ID of the workspace to update
        payload: Fields to update (name, description, email_alias)

    Returns:
        Updated workspace details
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Validate email_alias format if provided (and not being cleared)
    if payload.email_alias is not None and payload.email_alias != '':
        if not validate_email_alias(payload.email_alias):
            raise HttpError(
                400,
                "Invalid email alias format. Must start with a letter, be 2-64 characters, "
                "and contain only lowercase letters, numbers, hyphens, or underscores."
            )

    @sync_to_async
    def _update_workspace():
        try:
            workspace = Workspace.objects.select_related('project').get(
                id=workspace_id,
                project__organization=organization
            )

            # Update only provided fields
            if payload.name is not None:
                workspace.name = payload.name
            if payload.description is not None:
                workspace.description = payload.description
            if payload.email_alias is not None:
                # Empty string means clear the alias
                workspace.email_alias = payload.email_alias if payload.email_alias else None

            # Run model validation (includes cross-model uniqueness check)
            try:
                workspace.clean()
            except DjangoValidationError as e:
                # Convert Django ValidationError to HttpError
                error_messages = []
                for field, errors in e.message_dict.items():
                    error_messages.extend(errors)
                raise HttpError(400, '; '.join(error_messages))

            workspace.save()

            return {
                'id': workspace.id,
                'name': workspace.name,
                'slug': workspace.slug,
                'description': workspace.description,
                'project_id': workspace.project_id,
                'project_name': workspace.project.name,
                'parent_id': workspace.parent_id if workspace.parent else None,
                'level': workspace.level,
                'full_path': workspace.get_full_path(),
                'canonical_email': workspace.canonical_email,
                'email_alias': workspace.email_alias,
                'alias_email': workspace.alias_email,
                'created_at': workspace.created_at,
                'updated_at': workspace.updated_at,
            }
        except Workspace.DoesNotExist:
            raise HttpError(404, f"Workspace {workspace_id} not found or access denied")

    workspace_data = await _update_workspace()
    return WorkspaceDetailResponse(**workspace_data)
