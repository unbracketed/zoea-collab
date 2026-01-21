"""
Utility functions for organization and user management.

These functions help with common tasks like getting a user's organization,
checking permissions, and managing organization context.

Note: This module provides both sync and async versions of key functions.
Use async versions (prefixed with 'a') when calling from async views/endpoints.
"""

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationUser

User = get_user_model()


def get_user_organization(user):
    """
    Get the active organization for a user (synchronous version).

    For now, returns the first organization the user belongs to.
    In the future, this could support organization switching where users
    can select which organization context they're working in.

    Args:
        user: Django User instance

    Returns:
        Organization instance or None if user doesn't belong to any organization

    Example:
        org = get_user_organization(request.user)
        if org:
            messages = ChatMessage.objects.for_organization(org)
    """
    if not user or not user.is_authenticated:
        return None

    try:
        org_user = OrganizationUser.objects.filter(user=user).select_related('organization').first()
        return org_user.organization if org_user else None
    except OrganizationUser.DoesNotExist:
        return None


async def aget_user_organization(user):
    """
    Get the active organization for a user (async version).

    Use this version when calling from async views/endpoints.

    Args:
        user: Django User instance

    Returns:
        Organization instance or None if user doesn't belong to any organization

    Example:
        org = await aget_user_organization(request.user)
        if org:
            # Use organization
            pass
    """
    # Check if user is authenticated (this might trigger lazy loading)
    @sync_to_async
    def _check_user():
        return user and user.is_authenticated

    if not await _check_user():
        return None

    # Query the database for organization
    @sync_to_async
    def _get_org():
        try:
            org_user = OrganizationUser.objects.filter(user=user).select_related('organization').first()
            return org_user.organization if org_user else None
        except OrganizationUser.DoesNotExist:
            return None

    return await _get_org()


def require_organization(user):
    """
    Get organization or raise exception.

    Use this when an organization is absolutely required for the operation.

    Args:
        user: Django User instance

    Returns:
        Organization instance

    Raises:
        ValueError: If user is not associated with any organization

    Example:
        try:
            org = require_organization(request.user)
            # Proceed with operation
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
    """
    org = get_user_organization(user)
    if not org:
        raise ValueError("User is not associated with any organization")
    return org


def get_user_organizations(user):
    """
    Get all organizations a user belongs to.

    Useful for organization switching UI or checking if user has multiple
    organization memberships.

    Args:
        user: Django User instance

    Returns:
        QuerySet of Organization instances

    Example:
        orgs = get_user_organizations(request.user)
        if orgs.count() > 1:
            # Show organization selector
            pass
    """
    if not user or not user.is_authenticated:
        return Organization.objects.none()

    return Organization.objects.filter(
        organization_users__user=user
    ).distinct()


def is_organization_admin(user, organization):
    """
    Check if a user is an admin of a specific organization.

    Args:
        user: Django User instance
        organization: Organization instance

    Returns:
        bool: True if user is admin, False otherwise

    Example:
        if is_organization_admin(request.user, org):
            # Allow admin actions
            pass
    """
    if not user or not user.is_authenticated:
        return False

    try:
        org_user = OrganizationUser.objects.get(
            user=user,
            organization=organization
        )
        return org_user.is_admin
    except OrganizationUser.DoesNotExist:
        return False


def is_organization_owner(user, organization):
    """
    Check if a user is the owner of a specific organization.

    Args:
        user: Django User instance
        organization: Organization instance

    Returns:
        bool: True if user is owner, False otherwise

    Example:
        if is_organization_owner(request.user, org):
            # Allow owner-only actions
            pass
    """
    if not user or not user.is_authenticated:
        return False

    try:
        return organization.is_owner(user)
    except Exception:
        # Organization has no owner
        return False


def can_add_user_to_organization(organization):
    """
    Check if a new user can be added to the organization.

    Checks against the organization's max_users limit.

    Args:
        organization: Organization or Account instance

    Returns:
        bool: True if user can be added, False if at limit

    Example:
        if can_add_user_to_organization(org):
            # Proceed with invitation
            pass
        else:
            return JsonResponse({'error': 'User limit reached'}, status=400)
    """
    # If it's an Account instance (our custom model), use the method
    if hasattr(organization, 'can_add_user'):
        return organization.can_add_user()

    # Otherwise, no limit (for base Organization)
    return True


def get_user_default_project(user):
    """
    Get the default project for a user.

    Returns the first project in the user's organization. This is used when
    project_id is not specified in API requests.

    Args:
        user: Django User instance

    Returns:
        Project instance or None if no projects exist

    Example:
        project = get_user_default_project(request.user)
        if not project:
            # No projects - user needs to create one
            pass
    """
    from projects.models import Project

    organization = get_user_organization(user)
    if not organization:
        return None

    return Project.objects.filter(organization=organization).first()


async def aget_user_default_project(user):
    """
    Get the default project for a user (async version).

    Args:
        user: Django User instance

    Returns:
        Project instance or None if no projects exist
    """
    return await sync_to_async(get_user_default_project)(user)


def get_project_default_workspace(project):
    """
    Get the default workspace for a project.

    Returns the root workspace (parent=None) for the project. This is used when
    workspace_id is not specified in API requests.

    Args:
        project: Project instance

    Returns:
        Workspace instance or None if no workspaces exist

    Example:
        workspace = get_project_default_workspace(project)
        if not workspace:
            # No workspaces - shouldn't happen if signals work correctly
            pass
    """
    from workspaces.models import Workspace

    if not project:
        return None

    return Workspace.objects.filter(project=project, parent=None).first()


async def aget_project_default_workspace(project):
    """
    Get the default workspace for a project (async version).

    Args:
        project: Project instance

    Returns:
        Workspace instance or None if no workspaces exist
    """
    return await sync_to_async(get_project_default_workspace)(project)


def initialize_user_organization(
    user,
    org_name=None,
    subscription_plan='free',
    max_users=5,
):
    """
    Initialize a complete organization setup for a new user.

    This function creates:
    1. An organization (Account) with the user as owner
    2. OrganizationUser membership (user added as admin)
    3. OrganizationOwner record
    4. Default project, workspace, and clipboard (via signals)

    All operations are performed in an atomic transaction - if any step fails,
    everything is rolled back.

    Args:
        user: Django User instance
        org_name: Name for the organization (optional, defaults to "{username}'s Organization")
        subscription_plan: Subscription tier ('free', 'pro', or 'enterprise')
        max_users: Maximum users allowed in the organization

    Returns:
        dict with keys:
            - organization: The created Account/Organization instance
            - project: The default Project created by signals
            - workspace: The default Workspace created by signals
            - clipboard: The default Clipboard created by signals

    Raises:
        ValueError: If organization creation fails
        RuntimeError: If signals didn't create project/workspace/clipboard

    Example:
        from accounts.utils import initialize_user_organization

        # During user registration
        user = User.objects.create_user(username='alice', email='alice@example.com', password='...')
        result = initialize_user_organization(user)
        org = result['organization']
        project = result['project']
        workspace = result['workspace']
        clipboard = result['clipboard']
    """
    from django.db import transaction
    from organizations.models import OrganizationOwner, OrganizationUser
    from accounts.models import Account
    from projects.models import Project
    from workspaces.models import Workspace
    from context_clipboards.models import Clipboard

    # Generate org name if not provided
    if not org_name:
        if user.get_full_name():
            org_name = f"{user.get_full_name()}'s Organization"
        else:
            org_name = f"{user.username}'s Organization"

    try:
        with transaction.atomic():
            # Step 1: Create organization
            organization = Account.objects.create(
                name=org_name,
                subscription_plan=subscription_plan,
                max_users=max_users,
                billing_email=user.email,
            )

            # Step 2: Add user to organization as admin
            org_user = OrganizationUser.objects.create(
                organization=organization,
                user=user,
                is_admin=True,
            )

            # Step 3: Make user the owner
            OrganizationOwner.objects.create(
                organization=organization,
                organization_user=org_user,
            )

            # Step 4: Verify project and workspace were created by signals
            project = Project.objects.filter(organization=organization).first()
            if not project:
                raise RuntimeError(
                    "No project was created! Check that project creation signals are working."
                )

            workspace = Workspace.objects.filter(project=project, parent=None).first()
            if not workspace:
                raise RuntimeError(
                    "No workspace was created! Check that workspace creation signals are working."
                )

            # Step 5: Verify clipboard was created by signals
            clipboard = Clipboard.objects.filter(workspace=workspace, owner=user, is_active=True).first()
            if not clipboard:
                raise RuntimeError(
                    "No clipboard was created! Check that clipboard creation signals are working."
                )

            return {
                'organization': organization,
                'project': project,
                'workspace': workspace,
                'clipboard': clipboard,
            }

    except Exception as e:
        # Transaction will auto-rollback on exception
        raise ValueError(f"Failed to initialize user organization: {str(e)}") from e
