"""
Django Ninja API for project endpoints.
"""

from ninja import Router, File, UploadedFile
from ninja.errors import HttpError
from asgiref.sync import sync_to_async

from django.core.exceptions import ValidationError as DjangoValidationError
from accounts.utils import aget_user_organization
from .models import Project, THEME_CHOICES
from .email_utils import validate_email_alias
from .schemas import (
    ProjectListResponse,
    ProjectDetailResponse,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    AvatarUploadResponse,
)

router = Router()

# Valid theme choices for validation
VALID_THEMES = [choice[0] for choice in THEME_CHOICES]


@router.get("/projects", response=ProjectListResponse)
async def list_projects(request):
    """
    List all projects for the current user's organization.

    Returns:
        List of projects with metadata
    """
    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get projects
    @sync_to_async
    def _get_projects():
        projects = Project.objects.filter(
            organization=organization
        ).select_related('created_by').order_by('-created_at')

        project_list = []
        for project in projects:
            project_list.append({
                'id': project.id,
                'name': project.name,
                'slug': project.slug,
                'working_directory': project.working_directory,
                'worktree_directory': project.worktree_directory,
                'description': project.description,
                'color_theme': project.color_theme,
                'color': project.theme_color,
                'avatar_url': project.avatar_url,
                'use_primary_header': project.use_primary_header,
                'canonical_email': project.canonical_email,
                'email_alias': project.email_alias,
                'alias_email': project.alias_email,
                'created_at': project.created_at,
                'updated_at': project.updated_at,
            })

        return project_list

    projects = await _get_projects()

    return ProjectListResponse(
        projects=projects,
        total=len(projects)
    )


@router.post("/projects", response=ProjectDetailResponse)
async def create_project(request, payload: ProjectCreateRequest):
    """
    Create a new project for the current user's organization.

    Args:
        request: Django request object
        payload: Project creation data (name, description, color_theme)

    Returns:
        Created project details
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Validate color_theme if provided
    if payload.color_theme is not None and payload.color_theme not in VALID_THEMES:
        raise HttpError(400, f"Invalid color theme. Must be one of: {', '.join(VALID_THEMES)}")

    @sync_to_async
    def _create_project():
        project = Project.objects.create(
            organization=organization,
            name=payload.name,
            description=payload.description or "",
            color_theme=payload.color_theme,
            use_primary_header=payload.use_primary_header or False,
            created_by=request.user,
        )

        return {
            'id': project.id,
            'name': project.name,
            'slug': project.slug,
            'working_directory': project.working_directory,
            'worktree_directory': project.worktree_directory,
            'description': project.description,
            'color_theme': project.color_theme,
            'color': project.theme_color,
            'avatar_url': project.avatar_url,
            'use_primary_header': project.use_primary_header,
            'canonical_email': project.canonical_email,
            'email_alias': project.email_alias,
            'alias_email': project.alias_email,
            'created_at': project.created_at,
            'updated_at': project.updated_at,
        }

    project_data = await _create_project()
    return ProjectDetailResponse(**project_data)


@router.get("/projects/{project_id}", response=ProjectDetailResponse)
async def get_project(request, project_id: int):
    """
    Get a specific project with details.

    Args:
        request: Django request object
        project_id: ID of the project to fetch

    Returns:
        Project details

    Raises:
        HttpError: If project not found or user doesn't have access
    """
    # Get user's organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get project
    @sync_to_async
    def _get_project():
        try:
            project = Project.objects.select_related(
                'organization', 'created_by'
            ).get(
                id=project_id,
                organization=organization
            )

            return {
                'id': project.id,
                'name': project.name,
                'slug': project.slug,
                'working_directory': project.working_directory,
                'worktree_directory': project.worktree_directory,
                'description': project.description,
                'color_theme': project.color_theme,
                'color': project.theme_color,
                'avatar_url': project.avatar_url,
                'use_primary_header': project.use_primary_header,
                'canonical_email': project.canonical_email,
                'email_alias': project.email_alias,
                'alias_email': project.alias_email,
                'created_at': project.created_at,
                'updated_at': project.updated_at,
            }
        except Project.DoesNotExist:
            raise HttpError(404, f"Project {project_id} not found or access denied")

    project_data = await _get_project()

    return ProjectDetailResponse(**project_data)


@router.patch("/projects/{project_id}", response=ProjectDetailResponse)
async def update_project(request, project_id: int, payload: ProjectUpdateRequest):
    """
    Update a project's settings.

    Args:
        request: Django request object
        project_id: ID of the project to update
        payload: Fields to update (name, description, color_theme, email_alias)

    Returns:
        Updated project details
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Validate color_theme if provided
    if payload.color_theme is not None and payload.color_theme not in VALID_THEMES:
        raise HttpError(400, f"Invalid color theme. Must be one of: {', '.join(VALID_THEMES)}")

    # Validate email_alias format if provided (and not being cleared)
    if payload.email_alias is not None and payload.email_alias != '':
        if not validate_email_alias(payload.email_alias):
            raise HttpError(
                400,
                "Invalid email alias format. Must start with a letter, be 2-64 characters, "
                "and contain only lowercase letters, numbers, hyphens, or underscores."
            )

    @sync_to_async
    def _update_project():
        try:
            project = Project.objects.get(
                id=project_id,
                organization=organization
            )

            # Update only provided fields
            if payload.name is not None:
                project.name = payload.name
            if payload.description is not None:
                project.description = payload.description
            if payload.color_theme is not None:
                project.color_theme = payload.color_theme
            if payload.use_primary_header is not None:
                project.use_primary_header = payload.use_primary_header
            if payload.email_alias is not None:
                # Empty string means clear the alias
                project.email_alias = payload.email_alias if payload.email_alias else None

            # Run model validation (includes cross-model uniqueness check)
            try:
                project.clean()
            except DjangoValidationError as e:
                # Convert Django ValidationError to HttpError
                error_messages = []
                for field, errors in e.message_dict.items():
                    error_messages.extend(errors)
                raise HttpError(400, '; '.join(error_messages))

            project.save()

            return {
                'id': project.id,
                'name': project.name,
                'slug': project.slug,
                'working_directory': project.working_directory,
                'worktree_directory': project.worktree_directory,
                'description': project.description,
                'color_theme': project.color_theme,
                'color': project.theme_color,
                'avatar_url': project.avatar_url,
                'use_primary_header': project.use_primary_header,
                'canonical_email': project.canonical_email,
                'email_alias': project.email_alias,
                'alias_email': project.alias_email,
                'created_at': project.created_at,
                'updated_at': project.updated_at,
            }
        except Project.DoesNotExist:
            raise HttpError(404, f"Project {project_id} not found or access denied")

    project_data = await _update_project()
    return ProjectDetailResponse(**project_data)


@router.post("/projects/{project_id}/avatar", response=AvatarUploadResponse)
async def upload_avatar(request, project_id: int, avatar: UploadedFile = File(...)):
    """
    Upload a project avatar image.

    Args:
        request: Django request object
        project_id: ID of the project
        avatar: The image file to upload

    Returns:
        URL to the uploaded avatar
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if avatar.content_type not in allowed_types:
        raise HttpError(400, f"Invalid file type. Allowed: {', '.join(allowed_types)}")

    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    if avatar.size > max_size:
        raise HttpError(400, "File too large. Maximum size is 5MB")

    @sync_to_async
    def _upload_avatar():
        try:
            project = Project.objects.get(
                id=project_id,
                organization=organization
            )

            # Delete old avatar if exists
            if project.avatar:
                project.avatar.delete(save=False)

            # Save new avatar
            project.avatar.save(avatar.name, avatar, save=True)

            return project.avatar_url
        except Project.DoesNotExist:
            raise HttpError(404, f"Project {project_id} not found or access denied")

    avatar_url = await _upload_avatar()
    return AvatarUploadResponse(avatar_url=avatar_url)


@router.delete("/projects/{project_id}/avatar")
async def delete_avatar(request, project_id: int):
    """
    Delete a project's avatar image.

    Args:
        request: Django request object
        project_id: ID of the project

    Returns:
        Success message
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _delete_avatar():
        try:
            project = Project.objects.get(
                id=project_id,
                organization=organization
            )

            if project.avatar:
                project.avatar.delete(save=True)
                return True
            return False
        except Project.DoesNotExist:
            raise HttpError(404, f"Project {project_id} not found or access denied")

    deleted = await _delete_avatar()
    return {"success": True, "deleted": deleted}
