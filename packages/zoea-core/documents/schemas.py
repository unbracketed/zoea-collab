from __future__ import annotations

"""
Pydantic schemas for Documents API.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    """Base schema for document fields."""
    name: str
    description: str | None = ""
    file_size: int | None = None


class DocumentPreviewOut(BaseModel):
    """Schema for serialized previews returned alongside documents."""

    kind: str
    status: str
    url: str | None = None
    html: str | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None
    error: str | None = None


class DocumentOut(DocumentBase):
    """Schema for document output."""
    id: int
    organization_id: int
    organization_name: str
    project_id: int | None = None
    workspace_id: int | None = None
    document_type: str = Field(..., description="Type of document (Image, PDF, Markdown, etc.)")
    created_at: datetime
    updated_at: datetime
    created_by_id: int | None = None
    created_by_username: str | None = None
    folder_id: int | None = None
    folder_path: str | None = None

    # Type-specific fields (optional, populated based on document_type)
    content: str | None = None  # For TextDocument subclasses
    image_file: str | None = None  # For Image
    width: int | None = None  # For Image
    height: int | None = None  # For Image
    pdf_file: str | None = None  # For PDF
    page_count: int | None = None  # For PDF
    docx_file: str | None = None  # For WordDocument
    paragraph_count: int | None = None  # For WordDocument
    xlsx_file: str | None = None  # For SpreadsheetDocument
    sheet_count: int | None = None  # For SpreadsheetDocument
    has_header: bool | None = None  # For CSV
    delimiter: str | None = None  # For CSV
    react_flow_version: str | None = None  # For ReactFlowDiagram
    excalidraw_version: str | None = None  # For ExcalidrawDiagram
    yoopta_version: str | None = None  # For YooptaDocument
    file: str | None = None  # For FileDocument
    original_filename: str | None = None  # For FileDocument
    content_type: str | None = None  # For FileDocument
    preview: DocumentPreviewOut | None = None

    class Config:
        from_attributes = True


class ImageOut(DocumentOut):
    """Schema for image document output."""
    image_file: str
    width: int | None = None
    height: int | None = None


class PDFOut(DocumentOut):
    """Schema for PDF document output."""
    pdf_file: str
    page_count: int | None = None


class WordDocumentOut(DocumentOut):
    """Schema for Word document output."""
    docx_file: str
    paragraph_count: int | None = None


class SpreadsheetDocumentOut(DocumentOut):
    """Schema for Spreadsheet document output."""
    xlsx_file: str
    sheet_count: int | None = None


class DocumentHtmlResponse(BaseModel):
    """Schema for document HTML content response."""
    html: str = Field(..., description="HTML content of the document")
    document_id: int = Field(..., description="ID of the document")
    document_name: str = Field(..., description="Name of the document")


class TextDocumentOut(DocumentOut):
    """Schema for text document output."""
    content: str


class MarkdownOut(TextDocumentOut):
    """Schema for Markdown document output."""
    pass


class CSVOut(TextDocumentOut):
    """Schema for CSV document output."""
    has_header: bool
    delimiter: str


class DiagramOut(TextDocumentOut):
    """Schema for diagram document output."""
    diagram_type: str


class D2DiagramOut(DiagramOut):
    """Schema for D2 diagram document output."""
    pass


class ReactFlowDiagramOut(DiagramOut):
    """Schema for React Flow diagram document output."""
    react_flow_version: str | None = None




class DocumentListResponse(BaseModel):
    """Schema for paginated document list response."""
    documents: list[DocumentOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class FileSearchRequest(BaseModel):
    """Request payload for file search queries."""
    query: str = Field(..., min_length=1, description="Search prompt")
    project_id: int = Field(..., description="Project whose store will be queried")
    model_id: str | None = Field(None, description="Optional model override")
    max_results: int | None = Field(None, description="Maximum number of sources to return")
    metadata_filter: str | None = Field(None, description="Optional metadata filter expression")
    filters: dict[str, Any] | None = Field(
        None,
        description="Backend-specific filter payload (e.g., Chroma where clause).",
    )


class FileSearchSource(BaseModel):
    """Metadata for a single retrieved source."""
    title: str | None = None
    uri: str | None = None
    snippet: str | None = None


class FileSearchResponse(BaseModel):
    """Structured response for file search results."""
    answer: str
    sources: list[FileSearchSource] = Field(default_factory=list)
    store_id: str
    model_id: str


class FolderAncestor(BaseModel):
    """Schema for a folder ancestor in breadcrumb path."""
    id: int
    name: str


class FolderOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    parent_id: int | None = None
    is_system: bool = False
    organization_id: int
    project_id: int
    workspace_id: int
    path: str
    level: int
    ancestors: list[FolderAncestor] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FolderCreateRequest(BaseModel):
    name: str
    workspace_id: int
    description: str | None = None
    parent_id: int | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: int | None = None


class DocumentMoveRequest(BaseModel):
    folder_id: int | None = None


class DocumentImportIssue(BaseModel):
    path: str
    reason: str
    status: str = "skipped"
    detail: str | None = None


class DocumentImportSummary(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int
    total_files: int
    total_size: int
    root_folder_id: int | None = None
    root_folder_path: str | None = None
    issues: list[DocumentImportIssue] = Field(default_factory=list)


class DirectoryImportRequest(BaseModel):
    """Schema for importing documents from a filesystem directory."""

    path: str = Field(..., description="Absolute directory path on the server")
    project_id: int = Field(..., description="Project the documents belong to")
    workspace_id: int = Field(..., description="Workspace the documents belong to")
    folder_id: int | None = Field(None, description="Optional target folder id")
    create_root_folder: bool = Field(True, description="Create a root folder for the import")
    root_folder_name: str | None = Field(None, description="Override root folder name")
    on_conflict: Literal["skip", "rename", "overwrite"] = Field(
        "rename",
        description="Behavior when a document name already exists",
    )
    follow_symlinks: bool = Field(False, description="Follow symlinks during directory import")


class D2DiagramCreateRequest(BaseModel):
    """Schema for creating a D2 diagram document."""

    name: str = Field(..., description="Diagram name")
    description: str | None = Field(None, description="Optional description")
    content: str = Field(..., description="D2 diagram source content")
    project_id: int = Field(..., description="Project the document belongs to")
    workspace_id: int = Field(..., description="Workspace the document belongs to")
    folder_id: int | None = Field(None, description="Optional folder id")


class MermaidDiagramCreateRequest(BaseModel):
    """Schema for creating a Mermaid diagram document."""

    name: str = Field(..., description="Diagram name")
    description: str | None = Field(None, description="Optional description")
    content: str = Field(..., description="Mermaid diagram source content")
    project_id: int = Field(..., description="Project the document belongs to")
    workspace_id: int = Field(..., description="Workspace the document belongs to")
    folder_id: int | None = Field(None, description="Optional folder id")


class MarkdownCreateRequest(BaseModel):
    """Schema for creating a Markdown document."""

    name: str = Field(..., description="Document name")
    description: str | None = Field(None, description="Optional description")
    content: str = Field(..., description="Markdown content")
    project_id: int = Field(..., description="Project id")
    workspace_id: int = Field(..., description="Workspace id")
    folder_id: int | None = Field(None, description="Optional folder id")


class MarkdownUpdateRequest(BaseModel):
    """Schema for updating a Markdown document."""

    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Optional description")
    content: str | None = Field(None, description="Markdown content")


class ExcalidrawDiagramCreateRequest(BaseModel):
    """Schema for creating an Excalidraw diagram document."""

    name: str = Field(..., description="Diagram name")
    description: str | None = Field(None, description="Optional description")
    content: str = Field(..., description="Excalidraw JSON content")
    project_id: int = Field(..., description="Project the document belongs to")
    workspace_id: int = Field(..., description="Workspace the document belongs to")
    folder_id: int | None = Field(None, description="Optional folder id")
    excalidraw_version: str | None = Field(None, description="Excalidraw library version")


class ExcalidrawDiagramUpdateRequest(BaseModel):
    """Schema for updating an Excalidraw diagram document."""

    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Optional description")
    content: str | None = Field(None, description="Excalidraw JSON content")
    excalidraw_version: str | None = Field(None, description="Excalidraw library version")


class YooptaDocumentCreateRequest(BaseModel):
    """Schema for creating a Yoopta rich text document."""

    name: str = Field(..., description="Document name")
    description: str | None = Field(None, description="Optional description")
    content: str = Field(..., description="Yoopta JSON content")
    project_id: int = Field(..., description="Project the document belongs to")
    workspace_id: int = Field(..., description="Workspace the document belongs to")
    folder_id: int | None = Field(None, description="Optional folder id")
    yoopta_version: str | None = Field(None, description="Yoopta-Editor version")


class YooptaDocumentUpdateRequest(BaseModel):
    """Schema for updating a Yoopta rich text document."""

    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Optional description")
    content: str | None = Field(None, description="Yoopta JSON content")
    yoopta_version: str | None = Field(None, description="Yoopta-Editor version")


class YooptaExportResponse(BaseModel):
    """Schema for Yoopta document export response."""

    content: str = Field(..., description="Exported content in requested format")
    format: str = Field(..., description="Export format (html or markdown)")
    document_id: int = Field(..., description="ID of the exported document")
    document_name: str = Field(..., description="Name of the exported document")


# =============================================================================
# Tool Artifact Schemas (Issue #108)
# =============================================================================


class CreateDocumentFromArtifactRequest(BaseModel):
    """Schema for creating a document from a tool-generated artifact.

    Used by the frontend to save tool-generated images/files to the document library.
    """

    artifact_type: str = Field(
        ...,
        description="Type of artifact: 'image', 'code', 'document', 'diagram'",
    )
    file_path: str = Field(
        ...,
        description="Path to the generated file (must be within MEDIA_ROOT)",
    )
    workspace_id: int = Field(..., description="Workspace to save the document to")
    title: str | None = Field(None, description="Display title for the document")
    mime_type: str | None = Field(None, description="MIME type of the file")
    folder_id: int | None = Field(None, description="Optional folder to save to")
    metadata: dict | None = Field(
        default_factory=dict,
        description="Additional metadata to store with the document",
    )


class CreateDocumentFromArtifactResponse(BaseModel):
    """Response from creating a document from a tool artifact."""

    success: bool
    document_id: int | None = None
    document_type: str | None = None
    message: str
    document: DocumentOut | None = None
