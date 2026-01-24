"""
API endpoints for Documents.
"""

from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest
from ninja import File, Form, Query, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from accounts.utils import get_user_organization
from file_search import FileSearchRegistry
from file_search.exceptions import StoreError
from projects.models import Project

from .models import (
    D2Diagram,
    Document,
    ExcalidrawDiagram,
    Folder,
    Image,
    Markdown,
    MermaidDiagram,
    PDF,
    SpreadsheetDocument,
    WordDocument,
    YooptaDocument,
)
from .preview_service import get_preview_data
from .import_service import DocumentImportService, ImportLimitError, ImportValidationError
from .schemas import (
    CreateDocumentFromArtifactRequest,
    CreateDocumentFromArtifactResponse,
    D2DiagramCreateRequest,
    DirectoryImportRequest,
    DocumentHtmlResponse,
    DocumentListResponse,
    DocumentImportIssue,
    DocumentImportSummary,
    DocumentMoveRequest,
    DocumentOut,
    ExcalidrawDiagramCreateRequest,
    ExcalidrawDiagramUpdateRequest,
    FileSearchRequest,
    FileSearchResponse,
    FileSearchSource,
    FolderAncestor,
    FolderCreateRequest,
    FolderOut,
    FolderUpdateRequest,
    MarkdownCreateRequest,
    MarkdownUpdateRequest,
    MermaidDiagramCreateRequest,
    YooptaDocumentCreateRequest,
    YooptaDocumentUpdateRequest,
    YooptaExportResponse,
)
from .tool_artifact_service import ToolArtifactService

router = Router()


@router.get("/documents", response=DocumentListResponse, tags=["documents"])
def list_documents(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    document_type: str | None = None,
    folder_id: int | None = None,
    project_id: int | None = None,
    include_previews: bool = True,
    include_system: bool = Query(False, description="Include system/hidden folders and documents"),
):
    """
    List all documents for the authenticated user's organization.

    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20, max: 100)
    - search: Search in document name and description
    - document_type: Filter by document type (Image, PDF, Markdown, CSV, D2Diagram, ReactFlowDiagram)
    - project_id: Restrict results to a specific project (must belong to user's organization)
    """
    # Get user's organization
    organization = get_user_organization(request.user)
    if not organization:
        return {"documents": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

    queryset = (
        Document.objects.select_subclasses()
        .filter(organization=organization, is_trashed=False)
        .select_related("organization", "project", "created_by", "folder")
    )

    # Apply search filter
    if search:
        queryset = queryset.filter(name__icontains=search) | queryset.filter(
            description__icontains=search
        )

    # Apply document type filter
    # For multi-table inheritance, filter by checking the specific subclass path
    if document_type:
        # Map frontend type names to the filter path for that subclass
        # Uses Django's __ lookup syntax to traverse inheritance chain
        type_filter_mapping = {
            "image": "image__isnull",
            "pdf": "pdf__isnull",
            "worddocument": "worddocument__isnull",
            "spreadsheetdocument": "spreadsheetdocument__isnull",
            "markdown": "textdocument__markdown__isnull",
            "csv": "filedocument__csv__isnull",
            "d2diagram": "textdocument__d2diagram__isnull",
            "reactflowdiagram": "textdocument__reactflowdiagram__isnull",
            "jsoncanvas": "textdocument__jsoncanvas__isnull",
            "mermaiddiagram": "textdocument__mermaiddiagram__isnull",
            "excalidrawdiagram": "textdocument__excalidrawdiagram__isnull",
            "yooptadocument": "textdocument__yooptadocument__isnull",
            "filedocument": "filedocument__isnull",
        }
        filter_path = type_filter_mapping.get(document_type.lower())
        if filter_path:
            # Filter where the subclass exists (not null)
            queryset = queryset.filter(**{filter_path: False})

    project = None
    if project_id:
        project = _get_project(project_id, organization)
        queryset = queryset.filter(project=project)

    if folder_id:
        folder = _get_folder(folder_id, organization)
        # Validate folder belongs to the project if both are specified
        if project and folder.project_id != project.id:
            raise HttpError(400, "Folder must belong to the selected project")
        queryset = queryset.filter(folder=folder)

    # Exclude system/hidden folders unless explicitly included
    if not include_system:
        queryset = queryset.filter(Q(folder__isnull=True) | Q(folder__is_system=False))

    total = queryset.count()

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    # Get page of documents
    documents = queryset[offset : offset + page_size]

    # Convert to response schema
    document_list = [
        _serialize_document(doc, request, include_preview=include_previews) for doc in documents
    ]

    return DocumentListResponse(
        documents=document_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/documents/file-search", response=FileSearchResponse, tags=["documents"])
def query_file_search(request: HttpRequest, payload: FileSearchRequest):
    """
    Execute a file search query for a project's store.

    Uses the configured file search backend.
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(payload.project_id, organization)
    if not project.gemini_store_id:
        raise HttpError(400, "Project is not synced to file search.")

    try:
        store = FileSearchRegistry.get()
    except StoreError as exc:
        # Missing API key or misconfiguration
        raise HttpError(400, str(exc)) from exc

    backend_name = getattr(store, "backend_name", "")
    model_id = payload.model_id or (
        settings.GEMINI_MODEL_ID if backend_name == "gemini" else backend_name or "file-search"
    )

    try:
        filters = payload.filters
        if not filters and payload.metadata_filter and backend_name == "gemini":
            filters = {"metadata_filter": payload.metadata_filter}

        response = store.search(
            store_id=project.gemini_store_id,
            query=payload.query,
            max_results=payload.max_results or 5,
            filters=filters,
        )
    except Exception as exc:
        raise HttpError(502, f"File search query failed: {exc}") from exc

    return _serialize_file_search_response(
        response,
        store_id=project.gemini_store_id,
        model_id=model_id,
    )


# =============================================================================
# Tool Artifact Endpoint (Issue #108) - MUST come before /documents/{document_id}
# =============================================================================


@router.post(
    "/documents/from-artifact",
    response=CreateDocumentFromArtifactResponse,
    tags=["documents"],
)
def create_document_from_artifact(
    request: HttpRequest,
    payload: CreateDocumentFromArtifactRequest,
):
    """
    Create a document from a tool-generated artifact file.

    This endpoint allows the frontend to save images or other files
    generated by AI tools (like image generators) to the document library.

    Security:
    - File path must be within MEDIA_ROOT (no directory traversal)
    - File must exist
    - User must have access to the specified project
    """
    from pathlib import Path

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    # Get and validate project
    project = _get_project(payload.project_id, organization)

    # Security validation: ensure file path is within MEDIA_ROOT
    try:
        file_path = Path(payload.file_path).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()

        # Check for directory traversal attacks
        if not str(file_path).startswith(str(media_root)):
            raise HttpError(
                403,
                "Invalid file path: must be within media directory",
            )

        # Check file exists
        if not file_path.exists():
            raise HttpError(404, "File not found")

        if not file_path.is_file():
            raise HttpError(400, "Path is not a file")

    except (ValueError, OSError) as e:
        raise HttpError(400, f"Invalid file path: {e}") from e

    # Validate folder if provided
    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)
        if folder.project_id != project.id:
            raise HttpError(400, "Folder must belong to the selected project")

    # Create document using ToolArtifactService
    service = ToolArtifactService(
        organization=organization,
        project=project,
        created_by=request.user,
    )

    document = service.create_document_from_artifact(
        artifact_type=payload.artifact_type,
        file_path=str(file_path),
        title=payload.title,
        mime_type=payload.mime_type,
        metadata=payload.metadata,
    )

    if document is None:
        return CreateDocumentFromArtifactResponse(
            success=False,
            message=f"Failed to create document from artifact type '{payload.artifact_type}'",
        )

    # Update folder if provided (service doesn't handle folders yet)
    if folder:
        document.folder = folder
        document.save(update_fields=["folder"])

    return CreateDocumentFromArtifactResponse(
        success=True,
        document_id=document.id,
        document_type=document.get_type_name(),
        message="Document created successfully",
        document=_serialize_document(document, request),
    )


def _serialize_import_summary(summary):
    return DocumentImportSummary(
        created=summary.created,
        updated=summary.updated,
        skipped=summary.skipped,
        failed=summary.failed,
        total_files=summary.total_files,
        total_size=summary.total_size,
        root_folder_id=summary.root_folder_id,
        root_folder_path=summary.root_folder_path,
        issues=[
            DocumentImportIssue(
                path=issue.path,
                reason=issue.reason,
                status=issue.status,
                detail=issue.detail,
            )
            for issue in summary.issues
        ],
    )


@router.post("/documents/import/directory", response=DocumentImportSummary, tags=["documents"])
def import_directory(
    request: HttpRequest,
    payload: DirectoryImportRequest,
):
    """Import documents from a server-side directory path."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(payload.project_id, organization)

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    try:
        service = DocumentImportService(
            organization=organization,
            project=project,
            created_by=request.user,
            base_folder=folder,
            create_root_folder=payload.create_root_folder,
            root_folder_name=(payload.root_folder_name or "").strip() or None,
            on_conflict=payload.on_conflict,
        )
        summary = service.import_directory(
            payload.path,
            follow_symlinks=payload.follow_symlinks,
        )
    except (ImportLimitError, ImportValidationError) as exc:
        raise HttpError(400, str(exc)) from exc

    return _serialize_import_summary(summary)


@router.post("/documents/import/archive", response=DocumentImportSummary, tags=["documents"])
def import_archive(
    request: HttpRequest,
    archive_file: UploadedFile = File(...),
    project_id: int = Form(...),
    folder_id: int | None = Form(None),
    create_root_folder: bool = Form(True),
    root_folder_name: str | None = Form(None),
    on_conflict: str = Form("rename"),
):
    """Import documents from an uploaded archive."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(project_id, organization)

    folder = None
    if folder_id:
        folder = _get_folder(folder_id, organization)

    try:
        normalized_conflict = (on_conflict or "rename").strip().lower()
        service = DocumentImportService(
            organization=organization,
            project=project,
            created_by=request.user,
            base_folder=folder,
            create_root_folder=create_root_folder,
            root_folder_name=(root_folder_name or "").strip() or None,
            on_conflict=normalized_conflict,
        )
        summary = service.import_archive(archive_file)
    except (ImportLimitError, ImportValidationError) as exc:
        raise HttpError(400, str(exc)) from exc

    return _serialize_import_summary(summary)


## Folder endpoints - MUST come before /documents/{document_id} to avoid route conflicts
@router.get("/documents/folders", response=list[FolderOut], tags=["documents"])
def list_folders(
    request: HttpRequest,
    project_id: int | None = None,
    parent_id: int | None = None,
    include_system: bool = Query(False, description="Include system/hidden folders"),
):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    queryset = Folder.objects.filter(organization=organization).select_related(
        "parent", "project", "organization"
    )

    if not include_system:
        queryset = queryset.filter(is_system=False)

    if project_id:
        project = _get_project(project_id, organization)
        queryset = queryset.filter(project=project)

    if parent_id is not None:
        if parent_id == 0:
            queryset = queryset.filter(parent__isnull=True)
        else:
            parent = _get_folder(parent_id, organization)
            queryset = queryset.filter(parent=parent)

    queryset = queryset.order_by("tree_id", "lft")
    return [_serialize_folder(folder) for folder in queryset]


@router.post("/documents/folders", response=FolderOut, tags=["documents"])
def create_folder(request: HttpRequest, payload: FolderCreateRequest):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(payload.project_id, organization)
    parent = None
    if payload.parent_id:
        parent = _get_folder(payload.parent_id, organization)
        if parent.project_id != project.id:
            raise HttpError(400, "Parent folder must belong to the same project")

    folder = Folder.objects.create(
        name=payload.name,
        description=payload.description or "",
        project=project,
        organization=organization,
        parent=parent,
        created_by=request.user,
    )

    return _serialize_folder(folder)


@router.get("/documents/folders/{folder_id}", response=FolderOut, tags=["documents"])
def get_folder(request: HttpRequest, folder_id: int):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")
    folder = _get_folder(folder_id, organization)
    return _serialize_folder(folder)


@router.patch("/documents/folders/{folder_id}", response=FolderOut, tags=["documents"])
def update_folder(request: HttpRequest, folder_id: int, payload: FolderUpdateRequest):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    folder = _get_folder(folder_id, organization)

    if payload.name is not None:
        folder.name = payload.name
    if payload.description is not None:
        folder.description = payload.description

    if payload.parent_id is not None:
        if payload.parent_id == 0:
            folder.parent = None
        else:
            parent = _get_folder(payload.parent_id, organization)
            if parent.id == folder.id or parent.is_descendant_of(folder):
                raise HttpError(400, "Cannot move folder inside itself")
            if parent.project_id != folder.project_id:
                raise HttpError(400, "Parent folder must belong to the same project")
            folder.parent = parent

    folder.save()
    return _serialize_folder(folder)


@router.delete("/documents/folders/{folder_id}", tags=["documents"])
def delete_folder(request: HttpRequest, folder_id: int):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    folder = _get_folder(folder_id, organization)
    folder.delete()
    return {"success": True}


@router.get("/documents/{document_id}", response=DocumentOut, tags=["documents"])
def get_document(
    request: HttpRequest,
    document_id: int,
    include_preview: bool = True,
    project_id: int | None = None,
):
    """
    Get a specific document by ID.

    Only returns documents belonging to the user's organization.

    Query parameters:
    - include_preview: Include preview data (default: True)
    - project_id: Optional project ID to validate document belongs to the specified project.
      This is a security enhancement to prevent cross-project document access (ZoeaStudio-5kn).
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        # Build query filters
        filters = {"id": document_id, "organization": organization}

        # SECURITY: If project_id is provided, validate document belongs to that project
        if project_id is not None:
            filters["project_id"] = project_id

        document = (
            Document.objects.select_subclasses()
            .select_related("organization", "project", "created_by", "folder")
            .get(**filters)
        )
        return _serialize_document(document, request, include_preview=include_preview)
    except Document.DoesNotExist as exc:
        if project_id is not None:
            raise HttpError(
                404, "Document not found or does not belong to the specified project"
            ) from exc
        raise HttpError(404, "Document not found") from exc


@router.post("/documents/d2/create", response=DocumentOut, tags=["documents"])
def create_d2_document(request: HttpRequest, payload: D2DiagramCreateRequest):
    """Create and persist a D2 diagram document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        project = Project.objects.get(id=payload.project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    document = D2Diagram.objects.create(
        organization=organization,
        project=project,
        name=payload.name,
        description=payload.description or "",
        content=payload.content,
        created_by=request.user,
        file_size=len(payload.content.encode("utf-8")) if payload.content else 0,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.post("/documents/mermaid/create", response=DocumentOut, tags=["documents"])
def create_mermaid_document(request: HttpRequest, payload: MermaidDiagramCreateRequest):
    """Create and persist a Mermaid diagram document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        project = Project.objects.get(id=payload.project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    document = MermaidDiagram.objects.create(
        organization=organization,
        project=project,
        name=payload.name,
        description=payload.description or "",
        content=payload.content,
        created_by=request.user,
        file_size=len(payload.content.encode("utf-8")) if payload.content else 0,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.post("/documents/markdown/create", response=DocumentOut, tags=["documents"])
def create_markdown_document(request: HttpRequest, payload: MarkdownCreateRequest):
    """Create and persist a Markdown document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        project = Project.objects.get(id=payload.project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    document = Markdown.objects.create(
        organization=organization,
        project=project,
        name=payload.name,
        description=payload.description or "",
        content=payload.content,
        created_by=request.user,
        file_size=len(payload.content.encode("utf-8")) if payload.content else 0,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.patch("/documents/markdown/{document_id}", response=DocumentOut, tags=["documents"])
def update_markdown_document(
    request: HttpRequest, document_id: int, payload: MarkdownUpdateRequest
):
    """Update an existing Markdown document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Markdown.objects.get(id=document_id, organization=organization)
    except Markdown.DoesNotExist as exc:
        raise HttpError(404, "Markdown document not found") from exc

    if payload.name is not None:
        document.name = payload.name
    if payload.description is not None:
        document.description = payload.description
    if payload.content is not None:
        document.content = payload.content
        document.file_size = len(payload.content.encode("utf-8"))

    document.save()
    return _serialize_document(document, request)


@router.post("/documents/excalidraw/create", response=DocumentOut, tags=["documents"])
def create_excalidraw_document(request: HttpRequest, payload: ExcalidrawDiagramCreateRequest):
    """Create and persist an Excalidraw diagram document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        project = Project.objects.get(id=payload.project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    document = ExcalidrawDiagram.objects.create(
        organization=organization,
        project=project,
        name=payload.name,
        description=payload.description or "",
        content=payload.content,
        excalidraw_version=payload.excalidraw_version or "",
        created_by=request.user,
        file_size=len(payload.content.encode("utf-8")) if payload.content else 0,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.patch("/documents/excalidraw/{document_id}", response=DocumentOut, tags=["documents"])
def update_excalidraw_document(
    request: HttpRequest, document_id: int, payload: ExcalidrawDiagramUpdateRequest
):
    """Update an existing Excalidraw diagram document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = ExcalidrawDiagram.objects.get(id=document_id, organization=organization)
    except ExcalidrawDiagram.DoesNotExist as exc:
        raise HttpError(404, "Excalidraw document not found") from exc

    if payload.name is not None:
        document.name = payload.name
    if payload.description is not None:
        document.description = payload.description
    if payload.content is not None:
        document.content = payload.content
        document.file_size = len(payload.content.encode("utf-8"))
    if payload.excalidraw_version is not None:
        document.excalidraw_version = payload.excalidraw_version

    document.save()
    return _serialize_document(document, request)


@router.post("/documents/yoopta/create", response=DocumentOut, tags=["documents"])
def create_yoopta_document(request: HttpRequest, payload: YooptaDocumentCreateRequest):
    """Create and persist a Yoopta rich text document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        project = Project.objects.get(id=payload.project_id, organization=organization)
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)

    document = YooptaDocument.objects.create(
        organization=organization,
        project=project,
        name=payload.name,
        description=payload.description or "",
        content=payload.content,
        yoopta_version=payload.yoopta_version or "4.0",
        created_by=request.user,
        file_size=len(payload.content.encode("utf-8")) if payload.content else 0,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.patch("/documents/yoopta/{document_id}", response=DocumentOut, tags=["documents"])
def update_yoopta_document(
    request: HttpRequest, document_id: int, payload: YooptaDocumentUpdateRequest
):
    """Update an existing Yoopta rich text document."""

    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = YooptaDocument.objects.get(id=document_id, organization=organization)
    except YooptaDocument.DoesNotExist as exc:
        raise HttpError(404, "Yoopta document not found") from exc

    if payload.name is not None:
        document.name = payload.name
    if payload.description is not None:
        document.description = payload.description
    if payload.content is not None:
        document.content = payload.content
        document.file_size = len(payload.content.encode("utf-8"))
    if payload.yoopta_version is not None:
        document.yoopta_version = payload.yoopta_version

    document.save()
    return _serialize_document(document, request)


@router.get("/documents/yoopta/{document_id}/export", response=YooptaExportResponse, tags=["documents"])
def export_yoopta_document(
    request: HttpRequest,
    document_id: int,
    format: str = Query("markdown", description="Export format: 'html' or 'markdown'"),
):
    """
    Export a Yoopta document to HTML or Markdown format.

    Query parameters:
    - format: Export format ('html' or 'markdown', default: 'markdown')
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = YooptaDocument.objects.get(id=document_id, organization=organization)
    except YooptaDocument.DoesNotExist as exc:
        raise HttpError(404, "Yoopta document not found") from exc

    format_lower = format.lower()
    if format_lower not in ("html", "markdown"):
        raise HttpError(400, "Invalid format. Must be 'html' or 'markdown'.")

    if format_lower == "html":
        content = document.get_html_content()
    else:
        content = document.get_markdown_content()

    return YooptaExportResponse(
        content=content,
        format=format_lower,
        document_id=document.id,
        document_name=document.name,
    )


@router.post("/documents/images/upload", response=DocumentOut, tags=["documents"])
def upload_image_document(
    request: HttpRequest,
    image_file: UploadedFile = File(...),
    name: str = Form(...),
    project_id: int = Form(...),
    description: str | None = Form(""),
    folder_id: int | None = Form(None),
):
    """Upload an image file as a document scoped to a project."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(project_id, organization)

    folder = None
    if folder_id:
        folder = _get_folder(folder_id, organization)

    document_name = name.strip() or image_file.name or "Image"
    document = Image.objects.create(
        organization=organization,
        project=project,
        name=document_name,
        description=description or "",
        image_file=image_file,
        file_size=getattr(image_file, "size", None),
        created_by=request.user,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.post("/documents/pdfs/upload", response=DocumentOut, tags=["documents"])
def upload_pdf_document(
    request: HttpRequest,
    pdf_file: UploadedFile = File(...),
    name: str = Form(...),
    project_id: int = Form(...),
    description: str | None = Form(""),
    folder_id: int | None = Form(None),
):
    """Upload a PDF file as a document scoped to a project."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(project_id, organization)

    folder = None
    if folder_id:
        folder = _get_folder(folder_id, organization)

    # Validate content type
    content_type = getattr(pdf_file, "content_type", "")
    if content_type and content_type != "application/pdf":
        raise HttpError(400, "File must be a PDF document")

    document_name = name.strip() or pdf_file.name or "PDF Document"
    document = PDF.objects.create(
        organization=organization,
        project=project,
        name=document_name,
        description=description or "",
        pdf_file=pdf_file,
        created_by=request.user,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.post("/documents/docx/upload", response=DocumentOut, tags=["documents"])
def upload_docx_document(
    request: HttpRequest,
    docx_file: UploadedFile = File(...),
    name: str = Form(...),
    project_id: int = Form(...),
    description: str | None = Form(""),
    folder_id: int | None = Form(None),
):
    """Upload a Word document (.docx) scoped to a project."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(project_id, organization)

    folder = None
    if folder_id:
        folder = _get_folder(folder_id, organization)
        if folder.project_id != project.id:
            raise HttpError(400, "Folder must belong to the selected project")

    # Validate content type
    content_type = getattr(docx_file, "content_type", "")
    valid_types = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ]
    if content_type and content_type not in valid_types:
        raise HttpError(400, "File must be a Word document (.docx)")

    document_name = name.strip() or docx_file.name or "Word Document"
    document = WordDocument.objects.create(
        organization=organization,
        project=project,
        name=document_name,
        description=description or "",
        docx_file=docx_file,
        created_by=request.user,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.get("/documents/docx/{document_id}/html", response=DocumentHtmlResponse, tags=["documents"])
def get_docx_html(request: HttpRequest, document_id: int):
    """Get HTML representation of a Word document for viewing."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = WordDocument.objects.get(id=document_id, organization=organization)
    except WordDocument.DoesNotExist as exc:
        raise HttpError(404, "Word document not found") from exc

    html_content = document.get_html_content()
    return DocumentHtmlResponse(
        html=html_content,
        document_id=document.id,
        document_name=document.name,
    )


@router.post("/documents/xlsx/upload", response=DocumentOut, tags=["documents"])
def upload_xlsx_document(
    request: HttpRequest,
    xlsx_file: UploadedFile = File(...),
    name: str = Form(...),
    project_id: int = Form(...),
    description: str | None = Form(""),
    folder_id: int | None = Form(None),
):
    """Upload an Excel spreadsheet (.xlsx) scoped to a project."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    project = _get_project(project_id, organization)

    folder = None
    if folder_id:
        folder = _get_folder(folder_id, organization)
        if folder.project_id != project.id:
            raise HttpError(400, "Folder must belong to the selected project")

    # Validate content type
    content_type = getattr(xlsx_file, "content_type", "")
    valid_types = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]
    if content_type and content_type not in valid_types:
        raise HttpError(400, "File must be an Excel spreadsheet (.xlsx)")

    document_name = name.strip() or xlsx_file.name or "Spreadsheet"
    document = SpreadsheetDocument.objects.create(
        organization=organization,
        project=project,
        name=document_name,
        description=description or "",
        xlsx_file=xlsx_file,
        created_by=request.user,
        folder=folder,
    )

    return _serialize_document(document, request)


@router.get("/documents/xlsx/{document_id}/html", response=DocumentHtmlResponse, tags=["documents"])
def get_xlsx_html(request: HttpRequest, document_id: int):
    """Get HTML representation of a spreadsheet for viewing."""
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = SpreadsheetDocument.objects.get(id=document_id, organization=organization)
    except SpreadsheetDocument.DoesNotExist as exc:
        raise HttpError(404, "Spreadsheet not found") from exc

    html_content = document.get_html_content()
    return DocumentHtmlResponse(
        html=html_content,
        document_id=document.id,
        document_name=document.name,
    )


@router.post("/documents/{document_id}/move", response=DocumentOut, tags=["documents"])
def move_document(request: HttpRequest, document_id: int, payload: DocumentMoveRequest):
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Document.objects.select_related(
            "organization", "project", "created_by", "folder"
        ).get(id=document_id, organization=organization)
    except Document.DoesNotExist as exc:
        raise HttpError(404, "Document not found") from exc

    folder = None
    if payload.folder_id:
        folder = _get_folder(payload.folder_id, organization)
        if folder.project_id != document.project_id:
            document.project = folder.project

    document.folder = folder
    document.save()
    return _serialize_document(document, request)


# =============================================================================
# Trash Management Endpoints
# =============================================================================


@router.get("/documents/trash", response=list[DocumentOut], tags=["documents"])
def list_trashed_documents(
    request: HttpRequest,
    project_id: int | None = None,
):
    """
    List all trashed documents for the authenticated user's organization.

    Query parameters:
    - project_id: Optional project ID to filter trashed documents
    """
    organization = get_user_organization(request.user)
    if not organization:
        return []

    queryset = (
        Document.objects.select_subclasses()
        .filter(organization=organization, is_trashed=True)
        .select_related("organization", "project", "created_by")
        .order_by("-trashed_at")
    )

    if project_id:
        project = _get_project(project_id, organization)
        queryset = queryset.filter(project=project)

    return [_serialize_document(doc, request, include_preview=True) for doc in queryset]


@router.patch("/documents/{document_id}/rename", tags=["documents"])
def rename_document(request: HttpRequest, document_id: int, name: str = Query(...)):
    """
    Rename a document.

    Query parameters:
    - name: The new name for the document
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Document.objects.get(id=document_id, organization=organization)
    except Document.DoesNotExist as exc:
        raise HttpError(404, "Document not found") from exc

    document.name = name.strip()
    document.save(update_fields=["name", "updated_at"])
    return {"success": True, "name": document.name}


@router.post("/documents/{document_id}/trash", tags=["documents"])
def trash_document(request: HttpRequest, document_id: int):
    """
    Move a document to trash.

    The document's original folder is preserved so it can be restored later.
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Document.objects.get(id=document_id, organization=organization)
    except Document.DoesNotExist as exc:
        raise HttpError(404, "Document not found") from exc

    if document.is_trashed:
        raise HttpError(400, "Document is already in trash")

    document.move_to_trash()
    return {"success": True}


@router.post("/documents/{document_id}/restore", tags=["documents"])
def restore_document(request: HttpRequest, document_id: int, folder_id: int | None = Query(None)):
    """
    Restore a document from trash.

    Query parameters:
    - folder_id: Optional folder ID to restore to. If not provided,
                restores to the original folder if it still exists.
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Document.objects.get(id=document_id, organization=organization, is_trashed=True)
    except Document.DoesNotExist as exc:
        raise HttpError(404, "Trashed document not found") from exc

    # Validate target folder if provided
    if folder_id:
        folder = _get_folder(folder_id, organization)
        if folder.project_id != document.project_id:
            raise HttpError(400, "Target folder must belong to the same project")

    document.restore_from_trash(folder_id)
    return {"success": True}


@router.delete("/documents/{document_id}/permanent", tags=["documents"])
def permanently_delete_document(request: HttpRequest, document_id: int):
    """
    Permanently delete a trashed document.

    This action cannot be undone. Only documents that are already in trash can be permanently deleted.
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        document = Document.objects.get(id=document_id, organization=organization, is_trashed=True)
    except Document.DoesNotExist as exc:
        raise HttpError(404, "Trashed document not found") from exc

    document.delete()
    return {"success": True}


def _get_project(project_id: int, organization):
    try:
        return Project.objects.select_related("organization").get(
            id=project_id,
            organization=organization,
        )
    except Project.DoesNotExist as exc:
        raise HttpError(404, "Project not found") from exc


def _get_folder(folder_id: int, organization):
    try:
        return Folder.objects.select_related("organization", "project").get(
            id=folder_id,
            organization=organization,
        )
    except Folder.DoesNotExist as exc:
        raise HttpError(404, "Folder not found") from exc


def _serialize_folder(folder: Folder) -> FolderOut:
    # Get ancestors (excluding self) for breadcrumb navigation
    ancestors = [
        FolderAncestor(id=ancestor.id, name=ancestor.name)
        for ancestor in folder.get_ancestors()
    ]
    return FolderOut(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        parent_id=folder.parent_id,
        is_system=folder.is_system,
        organization_id=folder.organization_id,
        project_id=folder.project_id,
        path=folder.get_path(),
        level=folder.level,
        ancestors=ancestors,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _serialize_file_search_response(
    response,
    *,
    store_id: str,
    model_id: str,
) -> FileSearchResponse:
    sources: list[FileSearchSource] = []

    if hasattr(response, "answer"):
        answer = getattr(response, "answer", "") or ""
        for source in getattr(response, "sources", []) or []:
            sources.append(
                FileSearchSource(
                    title=getattr(source, "title", None),
                    uri=getattr(source, "uri", None),
                    snippet=getattr(source, "excerpt", None),
                )
            )
    else:
        answer = getattr(response, "text", "") or ""
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            candidate = candidates[0]
            grounding = getattr(candidate, "grounding_metadata", None)
            if grounding:
                for chunk in getattr(grounding, "grounding_chunks", []) or []:
                    context = getattr(chunk, "retrieved_context", None)
                    if not context:
                        continue

                    sources.append(
                        FileSearchSource(
                            title=getattr(context, "title", None),
                            uri=getattr(context, "uri", None),
                            snippet=getattr(context, "text", None),
                        )
                    )

    return FileSearchResponse(
        answer=answer,
        sources=sources,
        store_id=store_id,
        model_id=model_id,
    )


def _serialize_document(
    document: Document, request: HttpRequest | None = None, *, include_preview: bool = True
) -> DocumentOut:
    data = {
        "id": document.id,
        "name": document.name,
        "description": document.description or "",
        "file_size": document.file_size,
        "organization_id": document.organization.id,
        "organization_name": document.organization.name,
        "project_id": document.project_id,
        "document_type": document.get_type_name(),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "created_by_id": document.created_by.id if document.created_by else None,
        "created_by_username": document.created_by.username if document.created_by else None,
        "folder_id": document.folder_id,
        "folder_path": document.folder.get_path() if document.folder else None,
    }

    if hasattr(document, "content"):
        data["content"] = document.content or ""
    if hasattr(document, "image_file") and getattr(document, "image_file"):
        image_url = document.image_file.url
        if request:
            image_url = request.build_absolute_uri(image_url)
        data["image_file"] = image_url
    if hasattr(document, "width"):
        data["width"] = getattr(document, "width", None)
    if hasattr(document, "height"):
        data["height"] = getattr(document, "height", None)
    if hasattr(document, "pdf_file") and getattr(document, "pdf_file"):
        pdf_url = document.pdf_file.url
        if request:
            pdf_url = request.build_absolute_uri(pdf_url)
        data["pdf_file"] = pdf_url
    if hasattr(document, "file") and getattr(document, "file"):
        file_url = document.file.url
        if request:
            file_url = request.build_absolute_uri(file_url)
        data["file"] = file_url
    if hasattr(document, "original_filename"):
        data["original_filename"] = getattr(document, "original_filename", None)
    if hasattr(document, "content_type"):
        data["content_type"] = getattr(document, "content_type", None)
    if hasattr(document, "page_count"):
        data["page_count"] = getattr(document, "page_count", None)
    if hasattr(document, "docx_file") and getattr(document, "docx_file"):
        docx_url = document.docx_file.url
        if request:
            docx_url = request.build_absolute_uri(docx_url)
        data["docx_file"] = docx_url
    if hasattr(document, "paragraph_count"):
        data["paragraph_count"] = getattr(document, "paragraph_count", None)
    if hasattr(document, "xlsx_file") and getattr(document, "xlsx_file"):
        xlsx_url = document.xlsx_file.url
        if request:
            xlsx_url = request.build_absolute_uri(xlsx_url)
        data["xlsx_file"] = xlsx_url
    if hasattr(document, "sheet_count"):
        data["sheet_count"] = getattr(document, "sheet_count", None)
    if hasattr(document, "has_header"):
        data["has_header"] = getattr(document, "has_header", None)
        data["delimiter"] = getattr(document, "delimiter", None)
    if hasattr(document, "react_flow_version"):
        data["react_flow_version"] = getattr(document, "react_flow_version", None)
    if hasattr(document, "excalidraw_version"):
        data["excalidraw_version"] = getattr(document, "excalidraw_version", None)
    if hasattr(document, "yoopta_version"):
        data["yoopta_version"] = getattr(document, "yoopta_version", None)

    if include_preview:
        try:
            data["preview"] = get_preview_data(document, request=request)
        except Exception:
            data["preview"] = None

    return DocumentOut(**data)
