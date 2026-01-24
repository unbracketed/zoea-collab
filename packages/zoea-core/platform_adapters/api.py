"""
API endpoints for platform adapters.

Provides:
- Unified webhook receiver endpoint
- Platform connection CRUD
- Message listing and detail
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from pydantic import Field

from accounts.utils import get_user_organization

from .adapters import GenericWebhookAdapter
from .models import (
    PlatformMessage,
    ConnectionStatus,
    MessageStatus,
    PlatformConnection,
    PlatformType,
)

logger = logging.getLogger(__name__)

router = Router()


# =============================================================================
# Schemas
# =============================================================================


class PlatformConnectionCreate(Schema):
    """Schema for creating a platform connection."""

    platform_type: str = Field(..., description="Platform type (slack, discord, webhook, etc.)")
    name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Optional description")
    project_id: int | None = Field(None, description="Optional project to scope messages to")
    config: dict[str, Any] = Field(default_factory=dict, description="Platform-specific config")


class PlatformConnectionUpdate(Schema):
    """Schema for updating a platform connection."""

    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None


class PlatformConnectionOut(Schema):
    """Schema for platform connection response."""

    id: int
    connection_id: str
    platform_type: str
    name: str
    description: str
    status: str
    status_message: str
    webhook_url: str
    webhook_secret: str | None = None
    project_id: int | None
    message_count: int
    last_message_at: str | None
    created_at: str
    updated_at: str

    @staticmethod
    def from_model(
        conn: PlatformConnection, *, include_secret: bool = False
    ) -> "PlatformConnectionOut":
        return PlatformConnectionOut(
            id=conn.id,
            connection_id=str(conn.connection_id),
            platform_type=conn.platform_type,
            name=conn.name,
            description=conn.description,
            status=conn.status,
            status_message=conn.status_message,
            webhook_url=conn.get_webhook_url(),
            webhook_secret=conn.webhook_secret if include_secret else None,
            project_id=conn.project_id,
            message_count=conn.message_count,
            last_message_at=conn.last_message_at.isoformat() if conn.last_message_at else None,
            created_at=conn.created_at.isoformat(),
            updated_at=conn.updated_at.isoformat(),
        )


class PlatformMessageOut(Schema):
    """Schema for channel message response."""

    id: int
    message_id: str
    direction: str
    status: str
    status_message: str
    channel_id: str
    thread_id: str
    sender_id: str
    sender_name: str
    sender_email: str
    content: str
    content_type: str
    attachments: list[dict[str, Any]]
    metadata: dict[str, Any]
    received_at: str
    processed_at: str | None


class PlatformConnectionListResponse(Schema):
    """Response for listing platform connections."""

    connections: list[PlatformConnectionOut]
    total: int


class PlatformMessageListResponse(Schema):
    """Response for listing channel messages."""

    messages: list[PlatformMessageOut]
    total: int
    page: int
    page_size: int


# =============================================================================
# Platform Connection Endpoints
# =============================================================================


@router.get(
    "/connections",
    response=PlatformConnectionListResponse,
    tags=["platform-adapters"],
)
def list_connections(
    request: HttpRequest,
    platform_type: str | None = Query(None, description="Filter by platform type"),
    project_id: int | None = Query(None, description="Filter by project"),
    include_secret: bool = Query(
        False, description="Include webhook secret for webhook connections"
    ),
):
    """List all platform connections for the user's organization."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    queryset = PlatformConnection.objects.filter(organization=organization)

    if platform_type:
        queryset = queryset.filter(platform_type=platform_type)

    if project_id:
        queryset = queryset.filter(project_id=project_id)

    connections = list(queryset.order_by("-created_at"))

    return PlatformConnectionListResponse(
        connections=[
            PlatformConnectionOut.from_model(
                c,
                include_secret=(
                    include_secret and c.platform_type == PlatformType.WEBHOOK
                ),
            )
            for c in connections
        ],
        total=len(connections),
    )


@router.post(
    "/connections",
    response=PlatformConnectionOut,
    tags=["platform-adapters"],
)
def create_connection(request: HttpRequest, payload: PlatformConnectionCreate):
    """Create a new platform connection."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    # Validate platform type
    if payload.platform_type not in PlatformType.values:
        raise HttpError(400, f"Invalid platform type: {payload.platform_type}")

    # Validate project belongs to organization
    project = None
    if payload.project_id:
        from projects.models import Project

        try:
            project = Project.objects.get(id=payload.project_id, organization=organization)
        except Project.DoesNotExist:
            raise HttpError(400, "Project not found or doesn't belong to organization")

    connection = PlatformConnection.objects.create(
        organization=organization,
        project=project,
        platform_type=payload.platform_type,
        name=payload.name,
        description=payload.description,
        config=payload.config,
        status=ConnectionStatus.ACTIVE,
        created_by=request.user,
    )

    logger.info(f"Created platform connection {connection.id} ({connection.platform_type})")

    return PlatformConnectionOut.from_model(
        connection, include_secret=connection.platform_type == PlatformType.WEBHOOK
    )


@router.get(
    "/connections/{connection_id}",
    response=PlatformConnectionOut,
    tags=["platform-adapters"],
)
def get_connection(
    request: HttpRequest,
    connection_id: int,
    include_secret: bool = Query(
        False, description="Include webhook secret for webhook connections"
    ),
):
    """Get a specific platform connection."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        connection = PlatformConnection.objects.get(id=connection_id, organization=organization)
    except PlatformConnection.DoesNotExist:
        raise HttpError(404, "Connection not found")

    return PlatformConnectionOut.from_model(
        connection,
        include_secret=(
            include_secret and connection.platform_type == PlatformType.WEBHOOK
        ),
    )


@router.patch(
    "/connections/{connection_id}",
    response=PlatformConnectionOut,
    tags=["platform-adapters"],
)
def update_connection(
    request: HttpRequest,
    connection_id: int,
    payload: PlatformConnectionUpdate,
    include_secret: bool = Query(
        False, description="Include webhook secret for webhook connections"
    ),
):
    """Update a platform connection."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        connection = PlatformConnection.objects.get(id=connection_id, organization=organization)
    except PlatformConnection.DoesNotExist:
        raise HttpError(404, "Connection not found")

    if payload.name is not None:
        connection.name = payload.name
    if payload.description is not None:
        connection.description = payload.description
    if payload.config is not None:
        connection.config = payload.config
    if payload.status is not None:
        if payload.status not in ConnectionStatus.values:
            raise HttpError(400, f"Invalid status: {payload.status}")
        connection.status = payload.status

    connection.save()

    return PlatformConnectionOut.from_model(
        connection,
        include_secret=(
            include_secret and connection.platform_type == PlatformType.WEBHOOK
        ),
    )


@router.delete(
    "/connections/{connection_id}",
    tags=["platform-adapters"],
)
def delete_connection(request: HttpRequest, connection_id: int):
    """Delete a platform connection."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        connection = PlatformConnection.objects.get(id=connection_id, organization=organization)
    except PlatformConnection.DoesNotExist:
        raise HttpError(404, "Connection not found")

    connection_name = connection.name
    connection.delete()

    logger.info(f"Deleted platform connection {connection_id} ({connection_name})")

    return {"success": True, "message": f"Connection '{connection_name}' deleted"}


# =============================================================================
# Webhook Receiver Endpoint
# =============================================================================


@router.post(
    "/webhooks/{platform}/{connection_id}",
    tags=["platform-adapters"],
    auth=None,  # Webhooks use signature-based auth
)
def receive_webhook(
    request: HttpRequest,
    platform: str,
    connection_id: str,
):
    """
    Unified webhook receiver for all platforms.

    This endpoint receives webhooks from external platforms and:
    1. Validates the webhook signature
    2. Parses the message into normalized format
    3. Creates a PlatformMessage record
    4. Dispatches to the event system (if configured)

    Args:
        platform: Platform type (slack, discord, webhook, etc.)
        connection_id: UUID of the platform connection

    Returns:
        Success response or error details
    """
    # Find the connection
    try:
        connection = PlatformConnection.objects.get(
            connection_id=connection_id,
            platform_type=platform,
        )
    except PlatformConnection.DoesNotExist:
        logger.warning(f"Webhook received for unknown connection: {platform}/{connection_id}")
        raise HttpError(404, "Connection not found")

    # Check connection is active
    if connection.status != ConnectionStatus.ACTIVE:
        logger.warning(f"Webhook received for inactive connection: {connection.id}")
        return HttpResponse(status=200, content="Connection is not active")

    # Get the appropriate adapter
    adapter = _get_adapter(connection)

    # Validate the webhook
    validation = adapter.validate_webhook(request)
    if not validation.is_valid:
        logger.warning(f"Webhook validation failed: {validation.error_message}")
        raise HttpError(401, validation.error_message)

    # Parse the message
    parsed = adapter.parse_inbound(validation.payload)

    # Create the channel message
    message = adapter.create_channel_message(parsed, validation.payload)
    message.save()

    # Update connection stats
    connection.record_message()

    logger.info(
        f"Received webhook message {message.message_id} via {connection.name} "
        f"(should_process={parsed.should_process})"
    )

    # If message should be processed, dispatch to event system
    if parsed.should_process:
        _dispatch_to_event_system(message)

    return {
        "success": True,
        "message_id": str(message.message_id),
        "status": message.status,
    }


# =============================================================================
# Message Listing Endpoints
# =============================================================================


@router.get(
    "/connections/{connection_id}/messages",
    response=PlatformMessageListResponse,
    tags=["platform-adapters"],
)
def list_connection_messages(
    request: HttpRequest,
    connection_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status"),
):
    """List messages for a specific connection."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        connection = PlatformConnection.objects.get(id=connection_id, organization=organization)
    except PlatformConnection.DoesNotExist:
        raise HttpError(404, "Connection not found")

    queryset = PlatformMessage.objects.filter(connection=connection)

    if status:
        if status not in MessageStatus.values:
            raise HttpError(400, f"Invalid status: {status}")
        queryset = queryset.filter(status=status)

    total = queryset.count()
    offset = (page - 1) * page_size
    messages = list(queryset.order_by("-received_at")[offset : offset + page_size])

    return PlatformMessageListResponse(
        messages=[_message_to_schema(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_adapter(connection: PlatformConnection):
    """Get the appropriate adapter for a connection's platform type."""
    if connection.platform_type == PlatformType.WEBHOOK:
        return GenericWebhookAdapter(connection)
    # TODO: Add other adapters as they're implemented
    # elif connection.platform_type == PlatformType.SLACK:
    #     return SlackAdapter(connection)
    else:
        # Fall back to generic webhook for now
        return GenericWebhookAdapter(connection)


def _dispatch_to_event_system(message: PlatformMessage) -> None:
    """Dispatch a channel message to the event system."""
    try:
        from events.dispatcher import dispatch_event
        from events.models import EventType

        event_type = EventType.CHAT_MESSAGE
        if message.connection.platform_type == PlatformType.WEBHOOK:
            event_type = EventType.WEBHOOK_RECEIVED
        elif message.connection.platform_type == PlatformType.SLACK:
            event_type = EventType.SLACK_MESSAGE
        elif message.connection.platform_type == PlatformType.DISCORD:
            event_type = EventType.DISCORD_MESSAGE
        elif message.connection.platform_type == PlatformType.NOTION:
            event_type = EventType.NOTION_PAGE_UPDATED

        dispatch_event(
            event_type=event_type,
            source_type="platform_message",
            source_id=str(message.message_id),
            organization=message.organization,
            project=message.project,
            event_data=message.to_trigger_envelope(),
        )

        message.set_status(MessageStatus.PROCESSING)
        logger.info(f"Dispatched message {message.message_id} to event system")

    except Exception as e:
        logger.error(f"Failed to dispatch message {message.message_id}: {e}")
        message.set_status(MessageStatus.FAILED, str(e))


def _message_to_schema(message: PlatformMessage) -> PlatformMessageOut:
    """Convert a PlatformMessage to response schema."""
    return PlatformMessageOut(
        id=message.id,
        message_id=str(message.message_id),
        direction=message.direction,
        status=message.status,
        status_message=message.status_message,
        channel_id=message.channel_id,
        thread_id=message.thread_id,
        sender_id=message.sender_id,
        sender_name=message.sender_name,
        sender_email=message.sender_email,
        content=message.content,
        content_type=message.content_type,
        attachments=message.attachments,
        metadata=message.metadata,
        received_at=message.received_at.isoformat(),
        processed_at=message.processed_at.isoformat() if message.processed_at else None,
    )
