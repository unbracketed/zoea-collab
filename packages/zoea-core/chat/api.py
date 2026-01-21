"""
Django Ninja API for chat endpoints.

Supports context-aware agent routing based on view type, document context,
and requested capabilities. Uses the AgentRouter for intelligent dispatch.
"""

import base64
import logging
import mimetypes

from asgiref.sync import sync_to_async
from django.db import transaction
from ninja import Router
from ninja.errors import HttpError

from accounts.models import Account
from accounts.utils import (
    aget_user_organization,
    get_project_default_workspace,
    get_user_default_project,
)
from agents.context import AgentContext, AgentType, ViewContext
from agents.router import AgentRouter
from agents.skills import SKILL_LOADER_TOOL_NAME, build_skills_context_block
from context_clipboards.models import Clipboard
from context_clipboards.services import render_clipboard_to_markdown
from documents.models import Document, Image
from projects.models import Project
from workspaces.models import Workspace

from .agent_service import ChatAgentService
from .code_block_extractor import create_artifacts_from_tool_outputs
from .models import Conversation, Message
from .schemas import (
    ArtifactListResponse,
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ToolArtifactItem,
)
from .tool_agent_service import ToolAgentService, ToolArtifactData

router = Router()
logger = logging.getLogger(__name__)


@router.post("/chat", response=ChatResponse)
async def chat(request, payload: ChatRequest):
    """
    Send a message to the chat agent and get a response.

    This endpoint requires the user to be authenticated and associated with an organization.
    The organization context is automatically included in the agent's instructions.

    Supports context-aware routing based on:
    - view_type: Current UI view (chat, document_detail, excalidraw, etc.)
    - document_id/document_ids: Document context for RAG
    - folder_id/collection_id: Collection context for multi-doc RAG
    - rag_session_id: Existing RAG session to continue
    - requested_capabilities: Special capabilities like 'deep_research'

    Args:
        request: Django request object
        payload: Chat request with message and optional context

    Returns:
        Chat response with agent's reply and routing info

    Raises:
        HttpError: If user is not authenticated or not associated with an organization
    """
    # Get user's organization (async)
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    context = await sync_to_async(_prepare_chat_context)(request, organization, payload)
    account = context["account"]
    conversation = context["conversation"]
    conversation_messages = context["conversation_messages"]
    user_message_content = context["user_message_content"]
    image_contents = context["image_contents"]
    project = context["project"]
    workspace = context["workspace"]

    # Build agent context for routing
    agent_context = await _build_agent_context(payload, project, workspace)

    # Route to determine agent type and tools
    route_result = await sync_to_async(_route_request)(agent_context)
    agent_type = route_result.agent_type
    available_tools = route_result.tools

    tool_names = [t.name for t in available_tools]
    logger.info(
        f"Chat request routed to {agent_type.value} agent with {len(available_tools)} tools"
    )

    # Handle DOCUMENT_RAG routing - requires RAG session
    if agent_type == AgentType.DOCUMENT_RAG:
        if payload.rag_session_id:
            # Redirect to RAG session chat
            raise HttpError(
                400,
                f"For RAG sessions, use /api/document-rag/sessions/{payload.rag_session_id}/chat instead"
            )
        else:
            # Suggest creating a RAG session first
            raise HttpError(
                400,
                "Document-based chat requires a RAG session. "
                "Create one via POST /api/document-rag/sessions first."
            )

    # Build enhanced instructions with organization and context
    enhanced_instructions = await _build_agent_instructions(
        request.user,
        account,
        payload.instructions,
        agent_type,
        agent_context,
        available_tools=tool_names,
    )

    logger.info(
        f"Chat request from user '{request.user.username}' "
        f"(org: '{account.name}', subscription: '{account.subscription_plan}')"
    )
    if context["created_new_conversation"]:
        logger.info(
            "Created new conversation %s in project %s / workspace %s",
            conversation.id,
            project.name,
            workspace.name,
        )
    else:
        logger.info("Continuing conversation %s", conversation.id)
    logger.debug("Loaded %s historical messages", len(conversation_messages))

    # Check if conversation has images (multimodal content)
    # Images require ChatAgentService for vision model support
    def _has_images_in_conversation(msgs, img_contents):
        """Check if any message has multimodal image content."""
        if img_contents:
            return True
        for msg in msgs:
            if isinstance(msg.get("content"), list):
                # Multimodal format - check for image_url parts
                for part in msg["content"]:
                    if part.get("type") == "image_url":
                        return True
        return False

    has_images = _has_images_in_conversation(conversation_messages, image_contents)

    # Choose service based on available tools (but use ChatAgentService if images present)
    tools_called = []
    tool_artifacts = []  # Artifacts from tool execution (Issue #107) - for API response
    raw_tool_artifacts = []  # Raw ToolArtifactData for persistence
    if available_tools and not has_images:
        # Use ToolAgentService when tools are available (smolagents CodeAgent)
        logger.info(f"Using ToolAgentService with tools: {[t.name for t in available_tools]}")
        tool_service = ToolAgentService(
            project=project,
            tools=available_tools,
            context=payload.view_type or "chat",
        )

        # Build full prompt with conversation history for context
        full_prompt = _build_tool_agent_prompt(
            user_message_content,
            conversation_messages,
            enhanced_instructions,
        )

        result = await tool_service.chat(full_prompt, system_prompt=enhanced_instructions)
        response_text = result.response
        tools_called = result.tools_called
        model_used = tool_service.model_used

        # Extract tool artifacts (Issue #107)
        if result.artifacts:
            raw_tool_artifacts = result.artifacts  # Keep raw for persistence
            tool_artifacts = await _convert_artifacts_to_response(
                result.artifacts, request
            )
            logger.info(f"Tool generated {len(tool_artifacts)} artifacts")
    else:
        # Use ChatAgentService for simple chat or when images are present (vision support)
        if has_images:
            logger.info("Using ChatAgentService for vision (images present in conversation)")
        else:
            logger.info("Using ChatAgentService (no tools)")
        service = ChatAgentService(project=project)
        service.create_agent(name=payload.agent_name, instructions=enhanced_instructions)

        response_text = await service.chat(
            user_message_content,
            conversation_messages=conversation_messages,
            image_contents=image_contents,
        )
        model_used = service.model_used

    assistant_message = await _save_assistant_message(
        conversation,
        payload.agent_name,
        response_text,
        model_used,
        tool_artifacts=raw_tool_artifacts,
    )
    logger.info(
        "Saved assistant message %s for conversation %s",
        assistant_message.id,
        conversation.id,
    )

    # Build response with optional debug info
    response_data = {
        "response": response_text,
        "agent_name": payload.agent_name,
        "conversation_id": conversation.id,
    }

    # Include tool artifacts if any were generated (Issue #107)
    if tool_artifacts:
        response_data["tool_artifacts"] = tool_artifacts

    # Include debug information if requested
    if payload.debug:
        response_data["system_instructions"] = enhanced_instructions
        response_data["organization"] = account.name
        response_data["agent_type"] = agent_type.value
        response_data["tools_available"] = tool_names
        response_data["tools_called"] = tools_called

    return ChatResponse(**response_data)


async def _convert_artifacts_to_response(
    artifacts: list, request
) -> list[ToolArtifactItem]:
    """
    Convert ToolArtifactData objects to ToolArtifactItem response objects.

    Adds URLs for accessing file-based artifacts via the media server.
    Passes through content for inline artifacts (markdown tables, etc.).

    Args:
        artifacts: List of ToolArtifactData from ToolAgentService
        request: Django request object for building absolute URLs

    Returns:
        List of ToolArtifactItem for the API response
    """
    from pathlib import Path

    from django.conf import settings

    result = []
    media_root = Path(settings.MEDIA_ROOT)

    for artifact in artifacts:
        url = None
        content = getattr(artifact, "content", None)

        # For file-based artifacts, build URL from path
        if not artifact.path.startswith("_inline_"):
            artifact_path = Path(artifact.path)
            # If path is within MEDIA_ROOT, generate a URL
            try:
                relative_path = artifact_path.relative_to(media_root)
                url = request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")
            except ValueError:
                # Path is not within MEDIA_ROOT, no URL available
                logger.warning(f"Artifact path not in MEDIA_ROOT: {artifact.path}")

        result.append(
            ToolArtifactItem(
                type=artifact.type,
                path=artifact.path,
                mime_type=artifact.mime_type,
                title=artifact.title,
                url=url,
                content=content,
            )
        )

    return result


async def _build_agent_context(payload: ChatRequest, project, workspace) -> AgentContext:
    """Build AgentContext from request payload."""
    # Parse view type
    view_type = ViewContext.CHAT
    if payload.view_type:
        try:
            view_type = ViewContext(payload.view_type)
        except ValueError:
            pass

    # Get document if specified
    document = None
    if payload.document_id:
        document = await Document.objects.filter(id=payload.document_id).afirst()

    return AgentContext(
        project=project,
        workspace=workspace,
        view_type=view_type,
        document=document,
        document_ids=payload.document_ids,
        folder_id=payload.folder_id,
        collection_id=payload.collection_id,
        rag_session_id=payload.rag_session_id,
        requested_capabilities=payload.requested_capabilities,
    )


def _route_request(context: AgentContext):
    """Route request using AgentRouter (sync for DB access)."""
    router = AgentRouter()
    return router.route(context)


def _build_tool_agent_prompt(
    user_message: str,
    conversation_messages: list[dict],
    instructions: str,
) -> str:
    """
    Build a prompt for the tool agent with conversation history.

    Args:
        user_message: Current user message
        conversation_messages: Previous conversation messages
        instructions: System instructions (included for context)

    Returns:
        Combined prompt string
    """
    # Build conversation context if there's history
    if conversation_messages:
        history_lines = []
        for msg in conversation_messages[-10:]:  # Limit to recent history
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            history_lines.append(f"{role}: {content}")

        history_text = "\n".join(history_lines)
        return f"""Previous conversation:
{history_text}

Current message: {user_message}"""

    return user_message


async def _build_agent_instructions(
    user,
    account,
    base_instructions: str,
    agent_type: AgentType = None,
    agent_context: AgentContext = None,
    available_tools: list[str] | None = None,
) -> str:
    """
    Build agent instructions with organization and routing context (async).

    Args:
        user: Django User instance
        account: Account instance
        base_instructions: Base instructions from the request
        agent_type: The routed agent type (for context-specific instructions)
        agent_context: The agent context (for view-specific instructions)
        available_tools: List of tool names available to the agent

    Returns:
        Enhanced instructions including organization and routing context
    """
    # Build user context (async to handle lazy loading)
    @sync_to_async
    def _get_user_info():
        user_name = user.get_full_name() or user.username
        user_email = user.email
        return user_name, user_email

    user_name, user_email = await _get_user_info()

    # Build organization context (async)
    @sync_to_async
    def _get_org_info():
        org_name = account.name
        subscription_plan = account.get_subscription_plan_display()
        return org_name, subscription_plan

    org_name, subscription_plan = await _get_org_info()

    # Build context-specific instructions
    context_instructions = ""
    if agent_type == AgentType.EXCALIDRAW:
        context_instructions = """
You are assisting with an Excalidraw canvas. When asked to create diagrams:
- Use Mermaid syntax in code blocks for flowcharts, sequence diagrams, etc.
- Keep text content concise for canvas display.
- Suggest visual layouts and arrangements.
"""
    elif agent_type == AgentType.DEEP_RESEARCH:
        context_instructions = """
You are conducting deep research. Use multiple search passes to gather comprehensive information.
Synthesize findings from multiple sources and provide well-organized summaries.
"""

    # Add view context if available
    view_context = ""
    if agent_context and agent_context.document:
        view_context = f"\nCurrent document: {agent_context.document.name}"

    skills_context = ""
    if available_tools and SKILL_LOADER_TOOL_NAME in available_tools:
        skills_context = build_skills_context_block(
            context=agent_context.context_type if agent_context else None,
            tool_name=SKILL_LOADER_TOOL_NAME,
            include_locations=False,
        )

    # Get current date/time for temporal context (timezone-aware)
    from django.utils import timezone

    now = timezone.localtime()
    date_context = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")

    # Combine into enhanced instructions
    context = f"""
Current Date and Time: {date_context}

Organization Context:
- Organization: {org_name}
- Subscription: {subscription_plan}
- User: {user_name} ({user_email})
{view_context}
{skills_context}
{context_instructions}
{base_instructions}
""".strip()

    return context


@router.get("/conversations", response=ConversationListResponse)
async def list_conversations(request, project_id: int = None, workspace_id: int = None):
    """
    List all conversations for the current user, optionally filtered by project/workspace.

    Returns conversations ordered by most recently updated first.
    Each conversation includes basic metadata and message count.

    Args:
        request: Django request object
        project_id: Optional project ID to filter by
        workspace_id: Optional workspace ID to filter by

    Returns:
        List of conversations with metadata

    Raises:
        HttpError: If user is not authenticated or not associated with an organization
    """
    # Get user's organization (async)
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get conversations for this user (async)
    @sync_to_async
    def _get_conversations():
        from django.db.models import Count

        # Start with base filter
        conversations_query = Conversation.objects.filter(
            organization=organization,
            created_by=request.user
        )

        # Apply project filter if provided
        if project_id:
            conversations_query = conversations_query.filter(project_id=project_id)

        # Apply workspace filter if provided
        if workspace_id:
            conversations_query = conversations_query.filter(workspace_id=workspace_id)

        conversations = conversations_query.annotate(
            message_count=Count('messages')
        ).order_by('-updated_at')

        # Build response data
        conversation_list = []
        for conv in conversations:
            conversation_list.append({
                'id': conv.id,
                'title': conv.get_title(),
                'agent_name': conv.agent_name,
                'message_count': conv.message_count,
                'created_at': conv.created_at,
                'updated_at': conv.updated_at,
            })

        return conversation_list

    conversations = await _get_conversations()

    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations)
    )


@router.get("/conversations/{conversation_id}", response=ConversationDetailResponse)
async def get_conversation(request, conversation_id: int):
    """
    Get a specific conversation with all its messages.

    Args:
        request: Django request object
        conversation_id: ID of the conversation to fetch

    Returns:
        Conversation details with all messages

    Raises:
        HttpError: If conversation not found or user doesn't have access
    """
    from django.conf import settings
    from documents.models import CollectionItemSourceChannel

    # Get user's organization (async)
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Get conversation with messages (async)
    @sync_to_async
    def _get_conversation():
        try:
            conversation = Conversation.objects.select_related(
                'organization', 'created_by'
            ).prefetch_related('messages').get(
                id=conversation_id,
                organization=organization,
                created_by=request.user
            )

            # Build mapping of message_id -> tool artifacts from collection
            tool_artifacts_by_message = {}
            if conversation.artifacts_id:
                for item in conversation.artifacts.items.filter(
                    source_channel=CollectionItemSourceChannel.TOOL
                ):
                    message_id = item.source_metadata.get('message_id')
                    if message_id:
                        if message_id not in tool_artifacts_by_message:
                            tool_artifacts_by_message[message_id] = []

                        # Build artifact URL from path
                        artifact_path = item.source_metadata.get('path', '')
                        artifact_url = None
                        if artifact_path and not artifact_path.startswith('_inline'):
                            # Convert file path to media URL
                            media_root = str(settings.MEDIA_ROOT)
                            if artifact_path.startswith(media_root):
                                relative_path = artifact_path[len(media_root):].lstrip('/')
                                artifact_url = f"{settings.MEDIA_URL}{relative_path}"

                        tool_artifacts_by_message[message_id].append({
                            'type': item.source_metadata.get('type', 'unknown'),
                            'path': artifact_path,
                            'mime_type': item.source_metadata.get('mime_type'),
                            'title': item.source_metadata.get('title'),
                            'url': artifact_url,
                            'content': item.source_metadata.get('content'),
                        })

            # Build mapping of message_id -> attachments from email messages
            attachments_by_message = {}
            # Check for email_message reverse relation on each message
            # to get stored_attachments for email-originated messages
            from email_gateway.models import EmailMessage
            email_messages = EmailMessage.objects.filter(
                chat_message__in=conversation.messages.all()
            ).select_related('chat_message').prefetch_related('stored_attachments')

            for email_msg in email_messages:
                if email_msg.chat_message_id:
                    attachments = []
                    for att in email_msg.stored_attachments.all():
                        if att.file:
                            attachments.append({
                                'id': att.id,
                                'filename': att.filename,
                                'content_type': att.content_type,
                                'size': att.size,
                                'url': att.file.url,
                            })
                    if attachments:
                        attachments_by_message[email_msg.chat_message_id] = attachments

            # Build message list
            messages = []
            for msg in conversation.messages.all().order_by('created_at'):
                message_data = {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at,
                    'model_used': msg.model_used,
                }
                # Include tool artifacts if any exist for this message
                if msg.id in tool_artifacts_by_message:
                    message_data['tool_artifacts'] = tool_artifacts_by_message[msg.id]
                # Include attachments if any exist for this message
                if msg.id in attachments_by_message:
                    message_data['attachments'] = attachments_by_message[msg.id]
                messages.append(message_data)

            # Check if this conversation is linked to an email thread
            # Note: hasattr doesn't work for OneToOne reverse relations - must catch the exception
            from django.core.exceptions import ObjectDoesNotExist
            email_thread_id = None
            try:
                email_thread_id = conversation.email_thread.id
            except ObjectDoesNotExist:
                pass

            return {
                'id': conversation.id,
                'title': conversation.get_title(),
                'agent_name': conversation.agent_name,
                'messages': messages,
                'created_at': conversation.created_at,
                'updated_at': conversation.updated_at,
                'email_thread_id': email_thread_id,
            }
        except Conversation.DoesNotExist:
            raise HttpError(404, f"Conversation {conversation_id} not found or access denied")

    conversation_data = await _get_conversation()

    return ConversationDetailResponse(**conversation_data)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(request, conversation_id: int):
    """
    Delete a conversation and all its messages.

    Args:
        request: Django request object
        conversation_id: ID of the conversation to delete

    Returns:
        Success status

    Raises:
        HttpError: If conversation not found or user doesn't have access
    """
    # Get user's organization (async)
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    # Delete conversation (async)
    @sync_to_async
    def _delete_conversation():
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                organization=organization,
                created_by=request.user
            )
            conversation.delete()
            return True
        except Conversation.DoesNotExist:
            raise HttpError(404, f"Conversation {conversation_id} not found or access denied")

    await _delete_conversation()
    return {"success": True}


@router.get("/health")
def health_check(request):
    """
    Health check endpoint.

    Returns:
        Status information
    """
    return {"status": "ok", "service": "chat"}
def _prepare_chat_context(request, organization, payload):
    """
    Perform all database operations for a chat request inside a single transaction.
    """
    CLIPBOARD_TOKEN = "[Clipboard]"
    user = request.user

    with transaction.atomic():
        account = Account.objects.select_related().get(id=organization.id)

        if payload.project_id:
            try:
                project = Project.objects.get(id=payload.project_id, organization=organization)
            except Project.DoesNotExist:
                raise HttpError(
                    404, f"Project {payload.project_id} not found or access denied"
                )
        else:
            project = get_user_default_project(user)
            if not project:
                raise HttpError(400, "No projects found. Please create a project first.")

        if payload.workspace_id:
            try:
                workspace = Workspace.objects.get(id=payload.workspace_id, project=project)
            except Workspace.DoesNotExist:
                raise HttpError(
                    404, f"Workspace {payload.workspace_id} not found or access denied"
                )
        else:
            workspace = get_project_default_workspace(project)
            if not workspace:
                raise HttpError(400, f"No workspaces found for project {project.name}.")

        if payload.conversation_id:
            try:
                conversation = Conversation.objects.select_related(
                    "organization", "project", "workspace", "created_by"
                ).get(
                    id=payload.conversation_id,
                    organization=organization,
                    created_by=user,
                )
                created_new = False
            except Conversation.DoesNotExist:
                raise HttpError(
                    404,
                    f"Conversation {payload.conversation_id} not found or access denied",
                )
        else:
            conversation = Conversation.objects.create(
                organization=organization,
                project=project,
                workspace=workspace,
                created_by=user,
                agent_name=payload.agent_name,
                title="",
            )
            created_new = True

        # Expand clipboard token if present
        processed_message = payload.message
        image_contents: list[dict] = []
        if payload.clipboard_id and CLIPBOARD_TOKEN in processed_message:
            try:
                clipboard = Clipboard.objects.select_related(
                    "workspace__project__organization"
                ).get(id=payload.clipboard_id, owner=user, workspace=workspace)
            except Clipboard.DoesNotExist as exc:
                raise HttpError(404, "Clipboard not found or access denied") from exc

            clipboard_text = render_clipboard_to_markdown(clipboard, include_metadata=False)

            # Collect image attachments from clipboard items
            for item in clipboard.items.select_related("content_type"):
                if (
                    item.content_type
                    and item.content_type.app_label == "documents"
                    and item.content_type.model == "document"
                ):
                    try:
                        doc = Document.objects.select_subclasses().get(pk=item.object_id)
                    except Document.DoesNotExist:
                        continue
                    if isinstance(doc, Image) and getattr(doc, "image_file", None):
                        try:
                            file_path = doc.image_file.path
                            mime, _ = mimetypes.guess_type(doc.image_file.name)
                            mime = mime or "image/png"
                            with open(file_path, "rb") as f:
                                b64 = base64.b64encode(f.read()).decode("utf-8")
                            data_url = f"data:{mime};base64,{b64}"
                            image_contents.append({"type": "image_url", "image_url": {"url": data_url}})
                        except Exception:
                            continue

            processed_message = processed_message.replace(CLIPBOARD_TOKEN, clipboard_text or "")

        user_message = Message.objects.create(
            conversation=conversation,
            role="user",
            content=processed_message,
        )

        historical_messages = list(
            Message.objects.filter(conversation=conversation)
            .exclude(id=user_message.id)
            .order_by("created_at")
            .values("id", "role", "content")  # Include id for email attachment lookup
        )

        # Build mapping of message_id -> image data URLs for email attachments
        from email_gateway.models import EmailMessage as EmailMsg

        message_ids = [msg["id"] for msg in historical_messages]
        email_msgs = EmailMsg.objects.filter(
            chat_message_id__in=message_ids
        ).prefetch_related("stored_attachments")

        message_images: dict[int, list[dict]] = {}
        for email_msg in email_msgs:
            images = []
            for att in email_msg.stored_attachments.all():
                if att.file and att.content_type and att.content_type.startswith("image/"):
                    try:
                        with open(att.file.path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        images.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{att.content_type};base64,{b64}"}
                        })
                    except Exception:
                        continue
            if images:
                message_images[email_msg.chat_message_id] = images

        # Build conversation_messages with multimodal content for messages with images
        conversation_messages = []
        for msg in historical_messages:
            msg_id = msg["id"]
            if msg_id in message_images:
                # Multimodal format: content is a list of text + images
                content = [{"type": "text", "text": msg["content"]}] + message_images[msg_id]
            else:
                content = msg["content"]
            conversation_messages.append({"role": msg["role"], "content": content})

        return {
            "account": account,
            "project": project,
            "workspace": workspace,
            "conversation": conversation,
            "conversation_messages": conversation_messages,
            "created_new_conversation": created_new,
            "user_message_content": processed_message,
            "image_contents": image_contents,
        }


@sync_to_async
def _save_assistant_message(
    conversation, agent_name, response_text, model_used=None, tool_artifacts=None
):
    """Persist the assistant's reply and extract/persist artifacts.

    Args:
        conversation: The conversation to save to.
        agent_name: Name of the agent.
        response_text: The assistant's response text.
        model_used: The model that generated the response.
        tool_artifacts: Optional list of ToolArtifactData from tool execution.

    Returns:
        The created Message instance.
    """
    from chat.code_block_extractor import create_artifacts_from_code_blocks

    message = Message.objects.create(
        conversation=conversation,
        role="assistant",
        content=response_text,
        model_used=model_used or agent_name,
    )

    # Extract code blocks as artifacts
    create_artifacts_from_code_blocks(
        conversation=conversation,
        message=message,
        actor=conversation.created_by,
    )

    # Persist tool-generated artifacts (Issue #107)
    if tool_artifacts:
        create_artifacts_from_tool_outputs(
            conversation=conversation,
            message=message,
            tool_artifacts=tool_artifacts,
            actor=conversation.created_by,
        )

    return message


@router.get("/conversations/{conversation_id}/artifacts", response=ArtifactListResponse)
async def get_conversation_artifacts(request, conversation_id: int):
    """
    Get artifacts for a conversation.

    Args:
        request: Django request object
        conversation_id: ID of the conversation

    Returns:
        List of artifact items for the conversation

    Raises:
        HttpError: If conversation not found or user doesn't have access
    """
    organization = await aget_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")

    @sync_to_async
    def _get_artifacts():
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                organization=organization,
                created_by=request.user,
            )
        except Conversation.DoesNotExist:
            raise HttpError(404, f"Conversation {conversation_id} not found or access denied")

        # Return empty list if no artifacts collection
        if not conversation.artifacts_id:
            return {
                'items': [],
                'total': 0,
                'collection_id': None,
            }

        # Get artifact items
        items = conversation.artifacts.items.order_by('position')
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
            'collection_id': conversation.artifacts_id,
        }

    artifacts_data = await _get_artifacts()
    return ArtifactListResponse(**artifacts_data)
