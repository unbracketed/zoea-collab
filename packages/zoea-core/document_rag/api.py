"""
Django Ninja API for Document RAG endpoints.
"""

import logging

from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from projects.models import Project
from workspaces.models import Workspace

from .agent_service import DocumentRAGAgentService
from .models import RAGSession, RAGSessionMessage
from .schemas import (
    CreateRAGSessionRequest,
    DocumentSourceRef,
    RAGChatRequest,
    RAGChatResponse,
    RAGMessageResponse,
    RAGSessionDetailResponse,
    RAGSessionResponse,
)
from .session_manager import RAGSessionManager

router = Router(tags=["document-rag"])
logger = logging.getLogger(__name__)


@router.post("/sessions", response=RAGSessionResponse)
async def create_rag_session(request, payload: CreateRAGSessionRequest):
    """
    Create a new RAG session with selected documents.

    Uses the project-scoped file search store and scopes retrieval
    via metadata filters for the specified context (single document,
    folder, clipboard, or collection).

    Args:
        request: Django request object
        payload: Session creation parameters

    Returns:
        RAGSessionResponse with session details

    Raises:
        HttpError: If user is not authenticated or context is invalid
    """
    # Verify user organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get project and workspace
    try:
        project = await Project.objects.aget(id=payload.project_id, organization=organization)
        workspace = await Workspace.objects.aget(id=payload.workspace_id, project=project)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")
    except Workspace.DoesNotExist:
        raise HttpError(404, "Workspace not found")

    manager = RAGSessionManager()

    # Check for existing session if reuse is enabled
    if payload.reuse_existing:
        existing = await manager.find_active_session(
            context_type=payload.context_type,
            context_id=payload.context_id,
            workspace=workspace,
        )
        if existing:
            return RAGSessionResponse(
                session_id=str(existing.session_id),
                status=existing.status,
                document_count=existing.document_count,
                context_type=existing.context_type,
                context_display=existing.get_context_display(),
                created_at=existing.created_at,
            )

    # Create new session
    try:
        session = await manager.create_session(
            user=request.user,
            context_type=payload.context_type,
            context_id=payload.context_id,
            project=project,
            workspace=workspace,
        )
    except ValueError as e:
        raise HttpError(400, str(e))
    except Exception as e:
        logger.error(f"Failed to create RAG session: {e}")
        raise HttpError(500, "Failed to create RAG session")

    return RAGSessionResponse(
        session_id=str(session.session_id),
        status=session.status,
        document_count=session.document_count,
        context_type=session.context_type,
        context_display=session.get_context_display(),
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response=RAGSessionDetailResponse)
async def get_rag_session(request, session_id: str):
    """
    Get RAG session details including messages.

    Args:
        request: Django request object
        session_id: Session UUID

    Returns:
        RAGSessionDetailResponse with session details and messages

    Raises:
        HttpError: If session not found or not authorized
    """
    # Verify user organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get session
    manager = RAGSessionManager()
    session = await manager.get_session(session_id)

    if not session:
        raise HttpError(404, "Session not found or expired")

    # Verify ownership
    if session.organization_id != organization.id:
        raise HttpError(403, "Not authorized to access this session")

    # Get messages
    messages = []
    async for msg in session.messages.order_by("created_at"):
        sources = [DocumentSourceRef(**source) for source in (msg.retrieved_documents or [])]
        messages.append(
            RAGMessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                sources=sources,
                thinking_steps=msg.thinking_steps or [],
            )
        )

    return RAGSessionDetailResponse(
        session_id=str(session.session_id),
        status=session.status,
        document_count=session.document_count,
        context_type=session.context_type,
        context_display=session.get_context_display(),
        created_at=session.created_at,
        messages=messages,
    )


@router.post("/sessions/{session_id}/chat", response=RAGChatResponse)
async def rag_chat(request, session_id: str, payload: RAGChatRequest):
    """
    Send a message to the RAG agent.

    The agent will search through the session's indexed documents
    and provide a grounded response.

    Args:
        request: Django request object
        session_id: Session UUID
        payload: Chat message

    Returns:
        RAGChatResponse with agent response and sources

    Raises:
        HttpError: If session not found, not active, or unauthorized
    """
    # Verify user organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get session
    manager = RAGSessionManager()
    session = await manager.get_session(session_id)

    if not session:
        raise HttpError(404, "Session not found or expired")

    # Verify ownership
    if session.organization_id != organization.id:
        raise HttpError(403, "Not authorized to access this session")

    # Check session is active
    if session.status != RAGSession.Status.ACTIVE:
        raise HttpError(400, f"Session is not active (status: {session.status})")

    # Get project for LLM configuration (access via sync_to_async for async context)
    @sync_to_async
    def get_project():
        return session.project

    project = await get_project()

    # Save user message
    agent_service = DocumentRAGAgentService(session, project=project)
    await agent_service.save_message(
        role=RAGSessionMessage.Role.USER,
        content=payload.message,
    )

    # Get conversation history
    history = await agent_service.get_conversation_history()

    # Chat with agent
    response = await agent_service.chat(
        message=payload.message,
        conversation_history=history[:-1],  # Exclude the message we just added
    )

    # Save assistant message
    assistant_msg = await agent_service.save_message(
        role=RAGSessionMessage.Role.ASSISTANT,
        content=response.response,
        sources=response.sources,
        thinking_steps=response.thinking_steps,
        telemetry=response.telemetry,
    )

    # Format sources
    sources = []
    if payload.include_sources:
        for source in response.sources:
            sources.append(
                DocumentSourceRef(
                    title=source.get("title"),
                    uri=source.get("uri"),
                    excerpt=source.get("text", "")[:200] if source.get("text") else None,
                )
            )

    return RAGChatResponse(
        message_id=assistant_msg.id,
        response=response.response,
        sources=sources,
        thinking_steps=response.thinking_steps if payload.include_sources else None,
    )


@router.delete("/sessions/{session_id}")
async def close_rag_session(request, session_id: str):
    """
    Close a RAG session and cleanup resources.

    Marks the session as closed.

    Args:
        request: Django request object
        session_id: Session UUID

    Returns:
        Success message

    Raises:
        HttpError: If session not found or unauthorized
    """
    # Verify user organization
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get session
    manager = RAGSessionManager()
    session = await manager.get_session(session_id)

    if not session:
        raise HttpError(404, "Session not found")

    # Verify ownership
    if session.organization_id != organization.id:
        raise HttpError(403, "Not authorized to close this session")

    # Close session
    await manager.close_session(session)

    return {"status": "closed", "session_id": session_id}
