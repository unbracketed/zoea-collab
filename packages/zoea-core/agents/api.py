"""
Django Ninja API for Agent Orchestration endpoints.
"""

import logging

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from projects.models import Project

from .context import AgentContext, ViewContext
from .models import ProjectToolConfig
from .registry import ToolRegistry
from .router import AgentRouter
from .schemas import (
    RoutedChatRequest,
    RoutedChatResponse,
    RoutingInfo,
    ToolConfigUpdateRequest,
    ToolEnableRequest,
    ToolInfo,
    ToolListResponse,
    ToolStatusResponse,
)

router = Router(tags=["agents"])
logger = logging.getLogger(__name__)


@router.get("/tools", response=ToolListResponse)
async def list_tools(request, project_id: int):
    """
    List all available tools and their status for a project.

    Args:
        request: Django request object
        project_id: Project ID to check tool status for

    Returns:
        ToolListResponse with all tools and their status
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    try:
        project = await Project.objects.aget(id=project_id, organization=organization)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    registry = ToolRegistry.get_instance()
    tool_status = await sync_to_async(registry.get_tool_status)(project)

    tools = [
        ToolInfo(
            name=t["name"],
            description=t["description"],
            category=t["category"],
            is_enabled=t["is_enabled"],
            default_enabled=t["default_enabled"],
            requires_api_key=t["requires_api_key"],
            api_key_available=t["api_key_available"],
            supported_contexts=t["supported_contexts"],
            config_overrides=t["config_overrides"],
        )
        for t in tool_status
    ]

    return ToolListResponse(tools=tools, project_id=project_id)


@router.post("/tools/{tool_name}/enable", response=ToolStatusResponse)
async def enable_tool(request, tool_name: str, payload: ToolEnableRequest):
    """
    Enable a tool for a project.

    Creates or updates the ProjectToolConfig to enable the tool.

    Args:
        request: Django request object
        tool_name: Name of the tool to enable
        payload: Request with project_id

    Returns:
        ToolStatusResponse confirming the change
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    try:
        project = await Project.objects.aget(
            id=payload.project_id, organization=organization
        )
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    # Verify tool exists in registry
    registry = ToolRegistry.get_instance()
    if not registry.get_tool_definition(tool_name):
        raise HttpError(404, f"Tool '{tool_name}' not found in registry")

    # Update or create config
    config, created = await ProjectToolConfig.objects.aupdate_or_create(
        project=project,
        tool_name=tool_name,
        defaults={
            "organization": organization,
            "is_enabled": True,
            "created_by": request.user,
        },
    )

    action = "enabled" if created or not config.is_enabled else "already enabled"
    return ToolStatusResponse(
        tool_name=tool_name,
        is_enabled=True,
        message=f"Tool '{tool_name}' {action} for project '{project.name}'",
    )


@router.post("/tools/{tool_name}/disable", response=ToolStatusResponse)
async def disable_tool(request, tool_name: str, payload: ToolEnableRequest):
    """
    Disable a tool for a project.

    Creates or updates the ProjectToolConfig to disable the tool.

    Args:
        request: Django request object
        tool_name: Name of the tool to disable
        payload: Request with project_id

    Returns:
        ToolStatusResponse confirming the change
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    try:
        project = await Project.objects.aget(
            id=payload.project_id, organization=organization
        )
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    # Verify tool exists in registry
    registry = ToolRegistry.get_instance()
    if not registry.get_tool_definition(tool_name):
        raise HttpError(404, f"Tool '{tool_name}' not found in registry")

    # Update or create config
    config, created = await ProjectToolConfig.objects.aupdate_or_create(
        project=project,
        tool_name=tool_name,
        defaults={
            "organization": organization,
            "is_enabled": False,
            "created_by": request.user,
        },
    )

    return ToolStatusResponse(
        tool_name=tool_name,
        is_enabled=False,
        message=f"Tool '{tool_name}' disabled for project '{project.name}'",
    )


@router.patch("/tools/{tool_name}/config", response=ToolStatusResponse)
async def update_tool_config(
    request, tool_name: str, payload: ToolConfigUpdateRequest
):
    """
    Update tool-specific configuration for a project.

    Args:
        request: Django request object
        tool_name: Name of the tool to configure
        payload: Request with project_id and config

    Returns:
        ToolStatusResponse confirming the update
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    try:
        project = await Project.objects.aget(
            id=payload.project_id, organization=organization
        )
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    # Verify tool exists in registry
    registry = ToolRegistry.get_instance()
    if not registry.get_tool_definition(tool_name):
        raise HttpError(404, f"Tool '{tool_name}' not found in registry")

    # Update or create config
    config, created = await ProjectToolConfig.objects.aupdate_or_create(
        project=project,
        tool_name=tool_name,
        defaults={
            "organization": organization,
            "config_overrides": payload.config,
            "created_by": request.user,
        },
    )

    # If existing, merge config
    if not created:
        config.config_overrides.update(payload.config)
        await config.asave()

    return ToolStatusResponse(
        tool_name=tool_name,
        is_enabled=config.is_enabled,
        message=f"Configuration updated for tool '{tool_name}'",
    )


@router.post("/chat/route-info", response=RoutingInfo)
async def get_routing_info(request, payload: RoutedChatRequest):
    """
    Get routing information for a request without executing.

    Useful for debugging and understanding routing decisions.

    Args:
        request: Django request object
        payload: Chat request with context

    Returns:
        RoutingInfo showing how the request would be routed
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    try:
        project = await Project.objects.aget(
            id=payload.project_id, organization=organization
        )
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    # Get document if specified
    document = None
    if payload.document_id:
        from documents.models import Document

        try:
            document = await Document.objects.aget(id=payload.document_id)
        except Document.DoesNotExist:
            raise HttpError(404, "Document not found")

    # Build context
    try:
        view_type = ViewContext(payload.view_type)
    except ValueError:
        view_type = ViewContext.CHAT

    context = AgentContext(
        project=project,
        view_type=view_type,
        document=document,
        document_ids=payload.document_ids,
        folder_id=payload.folder_id,
        collection_id=payload.collection_id,
        rag_session_id=payload.rag_session_id,
        requested_capabilities=payload.requested_capabilities,
    )

    # Route (sync_to_async since router calls DB)
    agent_router = AgentRouter()
    result = await sync_to_async(agent_router.route)(context)

    return RoutingInfo(
        agent_type=result.agent_type.value,
        tools_available=[t.name for t in result.tools],
        context_type=context.context_type,
    )
