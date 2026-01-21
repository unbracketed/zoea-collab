"""Ninja routers for notebook endpoints.

Notebooks are DocumentCollection instances with collection_type=NOTEBOOK.
This API provides endpoints for managing notebooks, items, and notepad drafts.
"""

from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from workspaces.models import Workspace

from .models import (
    CollectionType,
    Document,
    DocumentCollection,
    DocumentCollectionItem,
    Folder,
    VirtualCollectionNode,
    YooptaDocument,
)
from .notebook_schemas import (
    NotebookActivateResponse,
    NotebookCreateRequest,
    NotebookDetailResponse,
    NotebookExportResponse,
    NotebookItemCreateRequest,
    NotebookItemListResponse,
    NotebookItemOperationResponse,
    NotebookItemReorderRequest,
    NotebookListResponse,
    NotebookNotepadDraftResponse,
    NotebookNotepadDraftUpdateRequest,
    NotebookSaveAsDocumentRequest,
    NotebookSaveAsDocumentResponse,
)
from .notebook_service import (
    NotebookService,
    get_notepad_draft_content,
    render_notebook_to_markdown,
    set_notepad_draft_content,
)
from .notebook_yoopta import build_shareable_yoopta_content_for_notebook
from .preview_service import get_preview_data

router = Router()


# =============================================================================
# Helper Functions
# =============================================================================


async def _require_organization(user):
    """Get user's organization or raise 403."""
    organization = await aget_user_organization(user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")
    return organization


async def _get_workspace(workspace_id: int, organization) -> Workspace:
    """Get workspace by ID, ensuring it belongs to the organization."""

    @sync_to_async
    def _fetch():
        try:
            return Workspace.objects.select_related("project__organization").get(
                id=workspace_id,
                project__organization=organization,
            )
        except Workspace.DoesNotExist as exc:
            raise HttpError(404, "Workspace not found or access denied") from exc

    return await _fetch()


async def _get_folder(folder_id: int, *, organization, workspace) -> Folder:
    """Get folder by ID, ensuring it belongs to the organization and workspace."""

    @sync_to_async
    def _fetch():
        try:
            return Folder.objects.get(
                id=folder_id,
                organization=organization,
                workspace=workspace,
            )
        except Folder.DoesNotExist as exc:
            raise HttpError(404, "Folder not found or access denied") from exc

    return await _fetch()


async def _get_notebook(
    notebook_id: int,
    *,
    organization,
    owner,
) -> DocumentCollection:
    """Get notebook by ID, ensuring it belongs to the owner and organization."""

    @sync_to_async
    def _fetch():
        try:
            return DocumentCollection.objects.select_related(
                "workspace__project__organization"
            ).get(
                id=notebook_id,
                collection_type=CollectionType.NOTEBOOK,
                owner=owner,
                workspace__project__organization=organization,
            )
        except DocumentCollection.DoesNotExist as exc:
            raise HttpError(404, "Notebook not found or access denied") from exc

    return await _fetch()


def _serialize_notebook(notebook: DocumentCollection) -> dict:
    """Serialize notebook basic fields."""
    return {
        "id": notebook.id,
        "name": notebook.name,
        "description": notebook.description,
        "workspace_id": notebook.workspace_id,
        "owner_id": notebook.owner_id,
        "is_active": notebook.is_active,
        "is_recent": notebook.is_recent,
        "activated_at": notebook.activated_at,
        "created_at": notebook.created_at,
        "updated_at": notebook.updated_at,
    }


def _serialize_notebook_with_metadata(notebook: DocumentCollection) -> dict:
    """Serialize notebook including metadata and sequence info."""
    base = _serialize_notebook(notebook)
    base.update(
        {
            "metadata": notebook.metadata or {},
            "sequence_head": notebook.sequence_head,
            "sequence_tail": notebook.sequence_tail,
        }
    )
    return base


def _serialize_item(item: DocumentCollectionItem, request=None) -> dict:
    """Serialize a notebook item."""
    content_type = None
    if item.content_type:
        content_type = f"{item.content_type.app_label}.{item.content_type.model}"

    # Use custom preview if available, otherwise generate from content_object
    preview = item.preview
    if not preview:
        try:
            if (
                content_type == "documents.document"
                and isinstance(item.content_object, Document)
            ):
                preview = get_preview_data(item.content_object, request=request)
        except Exception:
            preview = None

    return {
        "id": item.id,
        "notebook_id": item.collection_id,
        "position": item.position,
        "direction_added": item.direction_added,
        "is_pinned": item.is_pinned,
        "content_type": content_type,
        "object_id": item.object_id,
        "virtual_node_id": item.virtual_node_id,
        "source_channel": item.source_channel,
        "source_metadata": item.source_metadata or {},
        "preview": preview,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


async def _resolve_content_type(label: str) -> ContentType:
    """Resolve a content type from 'app_label.model' format."""
    try:
        app_label, model = label.split(".")
    except ValueError as exc:
        raise HttpError(400, "content_type must be in 'app_label.model' format") from exc

    @sync_to_async
    def _fetch():
        try:
            return ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist as exc:
            raise HttpError(404, f"Content type '{label}' was not found") from exc

    return await _fetch()


async def _get_virtual_node(
    node_id: int, workspace: Workspace
) -> VirtualCollectionNode:
    """Get virtual collection node by ID."""

    @sync_to_async
    def _fetch():
        try:
            return VirtualCollectionNode.objects.get(id=node_id, workspace=workspace)
        except VirtualCollectionNode.DoesNotExist as exc:
            raise HttpError(404, "Virtual collection node not found") from exc

    return await _fetch()


# =============================================================================
# Notebook CRUD Endpoints
# =============================================================================


@router.get("/", response=NotebookListResponse)
async def list_notebooks(
    request,
    workspace_id: int,
    include_recent: bool = False,
):
    """List notebooks for a workspace and user.

    Args:
        workspace_id: The workspace to list notebooks for.
        include_recent: Whether to include recently used (inactive) notebooks.

    Returns:
        NotebookListResponse with list of notebooks.
    """
    organization = await _require_organization(request.user)
    workspace = await _get_workspace(workspace_id, organization)

    @sync_to_async
    def _list():
        qs = (
            DocumentCollection.objects.for_workspace(workspace)
            .for_owner(request.user)
            .notebooks()
            .order_by("-is_active", "-activated_at", "-updated_at")
        )
        if not include_recent:
            qs = qs.filter(is_active=True)

        return [_serialize_notebook(nb) for nb in qs]

    notebooks = await _list()
    return NotebookListResponse(notebooks=notebooks, total=len(notebooks))


@router.post("/", response={201: NotebookDetailResponse})
async def create_notebook(request, payload: NotebookCreateRequest):
    """Create a new notebook scoped to the user/workspace.

    Args:
        payload: NotebookCreateRequest with workspace_id, name, description, activate.

    Returns:
        201 response with NotebookDetailResponse.
    """
    organization = await _require_organization(request.user)
    workspace = await _get_workspace(payload.workspace_id, organization)

    service = NotebookService(actor=request.user)

    @sync_to_async
    def _create():
        notebook = DocumentCollection.objects.create(
            organization=organization,
            workspace=workspace,
            owner=request.user,
            collection_type=CollectionType.NOTEBOOK,
            name=payload.name or f"{workspace.name} Notebook",
            description=payload.description or "",
            created_by=request.user,
        )
        if payload.activate:
            service.activate(notebook)
            notebook.refresh_from_db()
        return notebook

    notebook = await _create()
    response = NotebookDetailResponse(
        notebook=_serialize_notebook_with_metadata(notebook),
        items=[],
    )
    return 201, response


@router.get("/{notebook_id}", response=NotebookDetailResponse)
async def get_notebook(request, notebook_id: int, include_items: bool = False):
    """Return notebook metadata and optionally items.

    Args:
        notebook_id: The notebook ID.
        include_items: Whether to include items in the response.

    Returns:
        NotebookDetailResponse with notebook and optionally items.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    items: list[dict] | None = None
    if include_items:

        @sync_to_async
        def _get_items():
            return [
                _serialize_item(item, request)
                for item in notebook.items.order_by("position", "-created_at")
            ]

        items = await _get_items()

    return NotebookDetailResponse(
        notebook=_serialize_notebook_with_metadata(notebook),
        items=items,
    )


@router.post("/{notebook_id}/activate", response=NotebookActivateResponse)
async def activate_notebook(request, notebook_id: int):
    """Activate a notebook for the current user and workspace.

    Args:
        notebook_id: The notebook ID to activate.

    Returns:
        NotebookActivateResponse with the activated notebook.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )
    service = NotebookService(actor=request.user)

    @sync_to_async
    def _activate():
        service.activate(notebook)
        notebook.refresh_from_db()
        return notebook

    notebook = await _activate()
    return NotebookActivateResponse(
        notebook=_serialize_notebook_with_metadata(notebook)
    )


# =============================================================================
# Export Endpoint
# =============================================================================


@router.get("/{notebook_id}/export", response=NotebookExportResponse)
async def export_notebook(
    request,
    notebook_id: int,
    format: str = "markdown",
):
    """Export notebook contents to the specified format.

    Args:
        notebook_id: ID of the notebook to export.
        format: Export format (currently only 'markdown' is supported).

    Returns:
        NotebookExportResponse with exported content.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    if format != "markdown":
        raise HttpError(
            400, f"Unsupported export format: {format}. Only 'markdown' is supported."
        )

    @sync_to_async
    def _export():
        content = render_notebook_to_markdown(notebook, include_metadata=True)
        item_count = notebook.items.count()
        return content, item_count

    content, item_count = await _export()

    return NotebookExportResponse(
        format=format,
        content=content,
        item_count=item_count,
    )


# =============================================================================
# Notepad Draft Endpoints
# =============================================================================


@router.get("/{notebook_id}/notepad_draft", response=NotebookNotepadDraftResponse)
async def get_notebook_notepad_draft(
    request,
    notebook_id: int,
):
    """Return the stored Yoopta draft content for a notebook (if present).

    Args:
        notebook_id: The notebook ID.

    Returns:
        NotebookNotepadDraftResponse with draft content or null.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    return NotebookNotepadDraftResponse(content=get_notepad_draft_content(notebook))


@router.put("/{notebook_id}/notepad_draft", response=NotebookNotepadDraftResponse)
async def put_notebook_notepad_draft(
    request,
    notebook_id: int,
    payload: NotebookNotepadDraftUpdateRequest,
):
    """Create/replace the stored Yoopta draft content for a notebook.

    Args:
        notebook_id: The notebook ID.
        payload: NotebookNotepadDraftUpdateRequest with content.

    Returns:
        NotebookNotepadDraftResponse with updated draft content.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    @sync_to_async
    def _update():
        return set_notepad_draft_content(notebook, payload.content)

    notebook = await _update()
    return NotebookNotepadDraftResponse(content=get_notepad_draft_content(notebook))


@router.delete("/{notebook_id}/notepad_draft")
async def delete_notebook_notepad_draft(request, notebook_id: int):
    """Clear the stored notepad draft content for a notebook.

    Args:
        notebook_id: The notebook ID.

    Returns:
        Success response.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    @sync_to_async
    def _clear():
        set_notepad_draft_content(notebook, None)

    await _clear()
    return {"success": True}


# =============================================================================
# Save As Document Endpoint
# =============================================================================


@router.post(
    "/{notebook_id}/save_as_document",
    response={201: NotebookSaveAsDocumentResponse},
)
async def save_notebook_as_document(
    request,
    notebook_id: int,
    payload: NotebookSaveAsDocumentRequest,
):
    """Save the current notebook notepad as a shared YooptaDocument.

    Notepads are private by default (notebook-scoped). This endpoint creates a new
    YooptaDocument in the notebook's project/workspace to make the content shareable.

    Args:
        notebook_id: The notebook ID.
        payload: NotebookSaveAsDocumentRequest with name, description, folder_id.

    Returns:
        201 response with NotebookSaveAsDocumentResponse.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    folder = None
    if payload.folder_id:
        folder = await _get_folder(
            payload.folder_id,
            organization=organization,
            workspace=notebook.workspace,
        )

    @sync_to_async
    def _create_document():
        content_dict = build_shareable_yoopta_content_for_notebook(notebook)
        content_json = json.dumps(content_dict)
        document = YooptaDocument.objects.create(
            organization=organization,
            project=notebook.workspace.project,
            workspace=notebook.workspace,
            name=payload.name or f"{notebook.name} (Notepad)",
            description=payload.description or "",
            content=content_json,
            yoopta_version="4.0",
            created_by=request.user,
            file_size=len(content_json.encode("utf-8")) if content_json else 0,
            folder=folder,
        )
        return document

    document = await _create_document()
    return 201, NotebookSaveAsDocumentResponse(
        document_id=document.id,
        document_name=document.name,
    )


# =============================================================================
# Item Endpoints
# =============================================================================


@router.get("/{notebook_id}/items", response=NotebookItemListResponse)
async def list_notebook_items(
    request,
    notebook_id: int,
):
    """List items for a notebook.

    Args:
        notebook_id: The notebook ID.

    Returns:
        NotebookItemListResponse with list of items.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    @sync_to_async
    def _list_items():
        qs = notebook.items.order_by("position", "-created_at")
        return [_serialize_item(item, request) for item in qs]

    items = await _list_items()
    return NotebookItemListResponse(items=items, total=len(items))


@router.post("/{notebook_id}/items", response=NotebookItemOperationResponse)
async def create_notebook_item(
    request, notebook_id: int, payload: NotebookItemCreateRequest
):
    """Add an item to a notebook.

    Args:
        notebook_id: The notebook ID.
        payload: NotebookItemCreateRequest with item details.

    Returns:
        NotebookItemOperationResponse with the created item.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    content_type = None
    if payload.content_type:
        content_type = await _resolve_content_type(payload.content_type)
        if not payload.object_id:
            raise HttpError(400, "object_id is required when content_type is supplied")

    virtual_node = None
    if payload.virtual_node_id:
        virtual_node = await _get_virtual_node(
            payload.virtual_node_id, notebook.workspace
        )

    service = NotebookService(actor=request.user)

    @sync_to_async
    def _add():
        result = service.add_item(
            notebook=notebook,
            direction=payload.direction,
            content_type=content_type,
            object_id=payload.object_id,
            virtual_node=virtual_node,
            source_channel=payload.source_channel,
            source_metadata=payload.source_metadata,
            preview=payload.preview,
        )
        return result

    op_result = await _add()

    response = NotebookItemOperationResponse(
        item=_serialize_item(op_result.item, request),
    )
    return response


@router.delete("/{notebook_id}/items/{item_id}")
async def delete_notebook_item(request, notebook_id: int, item_id: int):
    """Remove an item from a notebook.

    Args:
        notebook_id: The notebook ID.
        item_id: The item ID to remove.

    Returns:
        Success response.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )

    @sync_to_async
    def _delete():
        try:
            item = notebook.items.get(id=item_id)
        except DocumentCollectionItem.DoesNotExist as exc:
            raise HttpError(404, "Notebook item not found") from exc
        item.delete()

    await _delete()
    return {"success": True}


@router.post("/{notebook_id}/items/reorder", response=NotebookActivateResponse)
async def reorder_notebook_items(
    request,
    notebook_id: int,
    payload: NotebookItemReorderRequest,
):
    """Bulk reorder notebook items.

    Args:
        notebook_id: The notebook ID.
        payload: NotebookItemReorderRequest with items to reorder.

    Returns:
        NotebookActivateResponse with updated notebook.
    """
    organization = await _require_organization(request.user)
    notebook = await _get_notebook(
        notebook_id, organization=organization, owner=request.user
    )
    service = NotebookService(actor=request.user)

    order_pairs = [(entry.item_id, entry.position) for entry in payload.items]

    @sync_to_async
    def _reorder():
        service.reorder_items(notebook=notebook, ordered_items=order_pairs)
        notebook.refresh_from_db()
        return notebook

    notebook = await _reorder()
    return NotebookActivateResponse(
        notebook=_serialize_notebook_with_metadata(notebook)
    )
