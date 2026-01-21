"""Ninja routers for clipboard endpoints.

.. deprecated:: 2.0
    This API module is deprecated. Use the notebook API endpoints at
    /api/notebooks/ instead. These endpoints will be removed in a future release.

    The frontend has been updated to use the new notebook API. This module
    is maintained for backward compatibility during the transition period.
"""

from __future__ import annotations

import json

from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import aget_user_organization
from workspaces.models import Workspace

from .models import Clipboard, ClipboardItem, VirtualClipboardNode
from .schemas import (
    ClipboardActivateResponse,
    ClipboardCreateRequest,
    ClipboardDetailResponse,
    ClipboardExportResponse,
    ClipboardNotepadDraftResponse,
    ClipboardNotepadDraftUpdateRequest,
    ClipboardSaveAsDocumentRequest,
    ClipboardSaveAsDocumentResponse,
    ClipboardItemCreateRequest,
    ClipboardItemListResponse,
    ClipboardItemOperationResponse,
    ClipboardItemReorderRequest,
    ClipboardListResponse,
)
from .notepad import (
    NOTEPAD_METADATA_CONTENT_KEY,
    NOTEPAD_METADATA_KEY,
    build_shareable_yoopta_content_for_clipboard,
    get_notepad_draft_content,
)
from .services import ClipboardService, render_clipboard_to_markdown
from documents.models import Document, Folder, YooptaDocument
from documents.preview_service import get_preview_data

router = Router()


async def _require_organization(user):
    organization = await aget_user_organization(user)
    if not organization:
        raise HttpError(403, "User is not associated with any organization")
    return organization


async def _get_workspace(workspace_id: int, organization) -> Workspace:
    @sync_to_async
    def _fetch():
        try:
            return Workspace.objects.select_related("project__organization").get(
                id=workspace_id,
                project__organization=organization,
            )
        except Workspace.DoesNotExist as exc:  # pragma: no cover - defensive
            raise HttpError(404, "Workspace not found or access denied") from exc

    return await _fetch()


async def _get_folder(folder_id: int, *, organization, workspace) -> Folder:
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


async def _get_clipboard(
    clipboard_id: int,
    *,
    organization,
    owner,
) -> Clipboard:
    @sync_to_async
    def _fetch():
        try:
            return Clipboard.objects.select_related("workspace__project__organization").get(
                id=clipboard_id,
                owner=owner,
                workspace__project__organization=organization,
            )
        except Clipboard.DoesNotExist as exc:
            raise HttpError(404, "Clipboard not found or access denied") from exc

    return await _fetch()


def _serialize_clipboard(clipboard: Clipboard) -> dict:
    return {
        "id": clipboard.id,
        "name": clipboard.name,
        "description": clipboard.description,
        "workspace_id": clipboard.workspace_id,
        "owner_id": clipboard.owner_id,
        "is_active": clipboard.is_active,
        "is_recent": clipboard.is_recent,
        "activated_at": clipboard.activated_at,
        "created_at": clipboard.created_at,
        "updated_at": clipboard.updated_at,
    }


def _serialize_clipboard_with_metadata(clipboard: Clipboard) -> dict:
    base = _serialize_clipboard(clipboard)
    base.update(
        {
            "metadata": clipboard.metadata or {},
            "sequence_head": clipboard.sequence_head,
            "sequence_tail": clipboard.sequence_tail,
        }
    )
    return base


def _serialize_item(item: ClipboardItem, request=None) -> dict:
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
        "clipboard_id": item.clipboard_id,
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
    try:
        app_label, model = label.split(".")
    except ValueError as exc:  # pragma: no cover - handled via 400
        raise HttpError(400, "content_type must be in 'app_label.model' format") from exc

    @sync_to_async
    def _fetch():
        try:
            return ContentType.objects.get(app_label=app_label, model=model)
        except ContentType.DoesNotExist as exc:
            raise HttpError(404, f"Content type '{label}' was not found") from exc

    return await _fetch()


async def _get_virtual_node(node_id: int, workspace: Workspace) -> VirtualClipboardNode:
    @sync_to_async
    def _fetch():
        try:
            return VirtualClipboardNode.objects.get(id=node_id, workspace=workspace)
        except VirtualClipboardNode.DoesNotExist as exc:
            raise HttpError(404, "Virtual clipboard node not found") from exc

    return await _fetch()


@router.get("/", response=ClipboardListResponse)
async def list_clipboards(
    request,
    workspace_id: int,
    include_recent: bool = False,
):
    """List clipboards for a workspace and user."""

    organization = await _require_organization(request.user)
    workspace = await _get_workspace(workspace_id, organization)

    @sync_to_async
    def _list():
        qs = (
            Clipboard.objects.for_workspace(workspace)
            .for_owner(request.user)
            .order_by("-is_active", "-activated_at", "-updated_at")
        )
        if not include_recent:
            qs = qs.filter(is_active=True)

        return [_serialize_clipboard(cb) for cb in qs]

    clipboards = await _list()
    return ClipboardListResponse(clipboards=clipboards, total=len(clipboards))


@router.post("/", response={201: ClipboardDetailResponse})
async def create_clipboard(request, payload: ClipboardCreateRequest):
    """Create a new clipboard scoped to the user/workspace."""

    organization = await _require_organization(request.user)
    workspace = await _get_workspace(payload.workspace_id, organization)

    service = ClipboardService(actor=request.user)

    @sync_to_async
    def _create():
        clipboard = Clipboard.objects.create(
            workspace=workspace,
            owner=request.user,
            name=payload.name or f"{workspace.name} Clipboard",
            description=payload.description or "",
        )
        if payload.activate:
            service.activate(clipboard)
            clipboard.refresh_from_db()
        return clipboard

    clipboard = await _create()
    response = ClipboardDetailResponse(
        clipboard=_serialize_clipboard_with_metadata(clipboard),
        items=[],
    )
    return 201, response


@router.get("/{clipboard_id}", response=ClipboardDetailResponse)
async def get_clipboard(request, clipboard_id: int, include_items: bool = False):
    """Return clipboard metadata and optionally items."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    items: list[dict] | None = None
    if include_items:
        @sync_to_async
        def _get_items():
            return [
                _serialize_item(item, request)
                for item in clipboard.items.order_by("position", "-created_at")
            ]

        items = await _get_items()

    return ClipboardDetailResponse(
        clipboard=_serialize_clipboard_with_metadata(clipboard),
        items=items,
    )


@router.get("/{clipboard_id}/export", response=ClipboardExportResponse)
async def export_clipboard(
    request,
    clipboard_id: int,
    format: str = "markdown",
):
    """Export clipboard contents to the specified format.

    Args:
        clipboard_id: ID of the clipboard to export
        format: Export format (currently only 'markdown' is supported)

    Returns:
        ClipboardExportResponse with exported content
    """
    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    # Validate format parameter
    if format != "markdown":
        raise HttpError(400, f"Unsupported export format: {format}. Only 'markdown' is supported.")

    @sync_to_async
    def _export():
        content = render_clipboard_to_markdown(clipboard, include_metadata=True)
        item_count = clipboard.items.count()
        return content, item_count

    content, item_count = await _export()

    return ClipboardExportResponse(
        format=format,
        content=content,
        item_count=item_count,
    )


@router.get("/{clipboard_id}/notepad_draft", response=ClipboardNotepadDraftResponse)
async def get_clipboard_notepad_draft(
    request,
    clipboard_id: int,
):
    """Return the stored Yoopta draft content for a clipboard (if present)."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    return ClipboardNotepadDraftResponse(content=get_notepad_draft_content(clipboard))


@router.put("/{clipboard_id}/notepad_draft", response=ClipboardNotepadDraftResponse)
async def put_clipboard_notepad_draft(
    request,
    clipboard_id: int,
    payload: ClipboardNotepadDraftUpdateRequest,
):
    """Create/replace the stored Yoopta draft content for a clipboard."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    @sync_to_async
    def _update():
        metadata = clipboard.metadata or {}
        raw_notepad = metadata.get(NOTEPAD_METADATA_KEY)
        notepad = raw_notepad if isinstance(raw_notepad, dict) else {}

        if payload.content is None:
            notepad.pop(NOTEPAD_METADATA_CONTENT_KEY, None)
            if notepad:
                metadata[NOTEPAD_METADATA_KEY] = notepad
            else:
                metadata.pop(NOTEPAD_METADATA_KEY, None)
        else:
            notepad[NOTEPAD_METADATA_CONTENT_KEY] = payload.content
            metadata[NOTEPAD_METADATA_KEY] = notepad

        clipboard.metadata = metadata
        clipboard.save(update_fields=["metadata"])
        return clipboard

    clipboard = await _update()
    return ClipboardNotepadDraftResponse(content=get_notepad_draft_content(clipboard))


@router.delete("/{clipboard_id}/notepad_draft")
async def delete_clipboard_notepad_draft(request, clipboard_id: int):
    """Clear the stored notepad draft content for a clipboard."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    @sync_to_async
    def _clear():
        metadata = clipboard.metadata or {}
        raw_notepad = metadata.get(NOTEPAD_METADATA_KEY)
        if not isinstance(raw_notepad, dict):
            metadata.pop(NOTEPAD_METADATA_KEY, None)
        else:
            raw_notepad.pop(NOTEPAD_METADATA_CONTENT_KEY, None)
            if raw_notepad:
                metadata[NOTEPAD_METADATA_KEY] = raw_notepad
            else:
                metadata.pop(NOTEPAD_METADATA_KEY, None)

        clipboard.metadata = metadata
        clipboard.save(update_fields=["metadata"])

    await _clear()
    return {"success": True}


@router.post(
    "/{clipboard_id}/save_as_document",
    response={201: ClipboardSaveAsDocumentResponse},
)
async def save_clipboard_as_document(
    request,
    clipboard_id: int,
    payload: ClipboardSaveAsDocumentRequest,
):
    """Save the current clipboard notepad as a shared YooptaDocument.

    Notepads are private by default (clipboard-scoped). This endpoint creates a new
    YooptaDocument in the clipboard's project/workspace to make the content shareable.
    """

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    folder = None
    if payload.folder_id:
        folder = await _get_folder(
            payload.folder_id,
            organization=organization,
            workspace=clipboard.workspace,
        )

    @sync_to_async
    def _create_document():
        content_dict = build_shareable_yoopta_content_for_clipboard(clipboard)
        content_json = json.dumps(content_dict)
        document = YooptaDocument.objects.create(
            organization=organization,
            project=clipboard.workspace.project,
            workspace=clipboard.workspace,
            name=payload.name or f"{clipboard.name} (Notepad)",
            description=payload.description or "",
            content=content_json,
            yoopta_version="4.0",
            created_by=request.user,
            file_size=len(content_json.encode("utf-8")) if content_json else 0,
            folder=folder,
        )
        return document

    document = await _create_document()
    return 201, ClipboardSaveAsDocumentResponse(
        document_id=document.id,
        document_name=document.name,
    )


@router.post("/{clipboard_id}/activate", response=ClipboardActivateResponse)
async def activate_clipboard(request, clipboard_id: int):
    """Activate a clipboard for the current user and workspace."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)
    service = ClipboardService(actor=request.user)

    @sync_to_async
    def _activate():
        service.activate(clipboard)
        clipboard.refresh_from_db()
        return clipboard

    clipboard = await _activate()
    return ClipboardActivateResponse(clipboard=_serialize_clipboard_with_metadata(clipboard))


@router.get("/{clipboard_id}/items", response=ClipboardItemListResponse)
async def list_clipboard_items(
    request,
    clipboard_id: int,
):
    """List items for a clipboard."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    @sync_to_async
    def _list_items():
        qs = clipboard.items.order_by("position", "-created_at")
        return [_serialize_item(item, request) for item in qs]

    items = await _list_items()
    return ClipboardItemListResponse(items=items, total=len(items))


@router.post("/{clipboard_id}/items", response=ClipboardItemOperationResponse)
async def create_clipboard_item(request, clipboard_id: int, payload: ClipboardItemCreateRequest):
    """Add an item to a clipboard."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    content_type = None
    if payload.content_type:
        content_type = await _resolve_content_type(payload.content_type)
        if not payload.object_id:
            raise HttpError(400, "object_id is required when content_type is supplied")

    virtual_node = None
    if payload.virtual_node_id:
        virtual_node = await _get_virtual_node(payload.virtual_node_id, clipboard.workspace)

    service = ClipboardService(actor=request.user)

    @sync_to_async
    def _add():
        result = service.add_item(
            clipboard=clipboard,
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

    response = ClipboardItemOperationResponse(
        item=_serialize_item(op_result.item, request),
    )
    return response


@router.delete("/{clipboard_id}/items/{item_id}")
async def delete_clipboard_item(request, clipboard_id: int, item_id: int):
    """Remove an item from a clipboard."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)

    @sync_to_async
    def _delete():
        try:
            item = clipboard.items.get(id=item_id)
        except ClipboardItem.DoesNotExist as exc:
            raise HttpError(404, "Clipboard item not found") from exc
        item.delete()

    await _delete()
    return {"success": True}


@router.post("/{clipboard_id}/items/reorder", response=ClipboardActivateResponse)
async def reorder_clipboard_items(
    request,
    clipboard_id: int,
    payload: ClipboardItemReorderRequest,
):
    """Bulk reorder clipboard items."""

    organization = await _require_organization(request.user)
    clipboard = await _get_clipboard(clipboard_id, organization=organization, owner=request.user)
    service = ClipboardService(actor=request.user)

    order_pairs = [(entry.item_id, entry.position) for entry in payload.items]

    @sync_to_async
    def _reorder():
        service.reorder_items(clipboard=clipboard, ordered_items=order_pairs)
        clipboard.refresh_from_db()
        return clipboard

    clipboard = await _reorder()
    return ClipboardActivateResponse(clipboard=_serialize_clipboard_with_metadata(clipboard))
