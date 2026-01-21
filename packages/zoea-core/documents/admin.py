"""
Admin interface for document models.

This module provides Django admin interfaces for Collection and Document models.
Document model uses multi-table inheritance, so each document type can have
its own admin interface.
"""

from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import (
    Collection,
    Document,
    DocumentCollection,
    DocumentCollectionItem,
    DocumentPreview,
    Image,
    PDF,
    SpreadsheetDocument,
    TextDocument,
    Markdown,
    CSV,
    JSONCanvas,
    D2Diagram,
    ReactFlowDiagram,
    MermaidDiagram,
    ExcalidrawDiagram,
    WordDocument,
    YooptaDocument,
    Folder,
    VirtualCollectionNode,
)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    """
    Admin interface for Collection management (LEGACY).

    DEPRECATED: This model is superseded by DocumentCollection.
    Displays collections scoped to projects and workspaces with document counts.
    """
    list_display = [
        'name',
        'organization',
        'project',
        'workspace',
        'document_count',
        'created_by',
        'created_at'
    ]
    list_filter = ['organization', 'project', 'workspace', 'created_at']
    search_fields = ['name', 'description', 'organization__name', 'project__name', 'workspace__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'project', 'workspace', 'created_by']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'project', 'workspace', 'name', 'description']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def document_count(self, obj):
        """Display number of documents in this collection."""
        return obj.documents.count()
    document_count.short_description = "Documents"

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'organization',
            'project',
            'workspace',
            'created_by'
        ).prefetch_related('documents')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Base admin interface for Document model.

    Shows only common fields. Use specific admin classes (ImageAdmin, PDFAdmin, etc.)
    for type-specific functionality.
    """
    list_display = [
        'name',
        'organization',
        'project',
        'workspace',
        'get_type_name',
        'file_size_display',
        'created_by',
        'created_at'
    ]
    list_filter = ['organization', 'project', 'workspace', 'created_at']
    search_fields = ['name', 'description', 'organization__name', 'project__name', 'workspace__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['organization', 'project', 'workspace', 'created_by', 'folder']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'project', 'workspace', 'folder', 'name', 'description']
        }),
        ('File Metadata', {
            'fields': ['file_size']
        }),
        ('Collections', {
            'fields': ['collections']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = "File Size"

    def get_queryset(self, request):
        """Optimize queryset with select_related, prefetch_related, and select_subclasses."""
        qs = super().get_queryset(request)
        return qs.select_subclasses().select_related(
            'organization',
            'project',
            'workspace',
            'created_by',
            'folder',
        ).prefetch_related('collections')


@admin.register(Folder)
class FolderAdmin(MPTTModelAdmin):
    list_display = ['name', 'workspace', 'project', 'organization', 'parent', 'created_by', 'created_at']
    search_fields = ['name', 'description', 'workspace__name', 'project__name', 'organization__name']
    list_filter = ['organization', 'workspace']
    raw_id_fields = ['organization', 'project', 'workspace', 'parent', 'created_by']
    ordering = ['tree_id', 'lft']


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    """Admin interface for Image documents."""
    list_display = [
        'name',
        'organization',
        'image_file',
        'width',
        'height',
        'file_size_display',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'width', 'height']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Image File', {
            'fields': ['image_file', 'width', 'height']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = "File Size"


@admin.register(PDF)
class PDFAdmin(admin.ModelAdmin):
    """Admin interface for PDF documents."""
    list_display = [
        'name',
        'organization',
        'pdf_file',
        'page_count',
        'file_size_display',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('PDF File', {
            'fields': ['pdf_file', 'page_count']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = "File Size"


@admin.register(WordDocument)
class WordDocumentAdmin(admin.ModelAdmin):
    """Admin interface for Word documents."""
    list_display = [
        'name',
        'organization',
        'docx_file',
        'paragraph_count',
        'file_size_display',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Word File', {
            'fields': ['docx_file', 'paragraph_count']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = "File Size"


@admin.register(SpreadsheetDocument)
class SpreadsheetDocumentAdmin(admin.ModelAdmin):
    """Admin interface for Spreadsheet documents."""
    list_display = [
        'name',
        'organization',
        'xlsx_file',
        'sheet_count',
        'file_size_display',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Spreadsheet File', {
            'fields': ['xlsx_file', 'sheet_count']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def file_size_display(self, obj):
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = "File Size"


@admin.register(Markdown)
class MarkdownAdmin(admin.ModelAdmin):
    """Admin interface for Markdown documents."""
    list_display = ['name', 'organization', 'content_preview', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Content', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "Content Preview"


@admin.register(CSV)
class CSVAdmin(admin.ModelAdmin):
    """Admin interface for CSV documents."""
    list_display = [
        'name',
        'organization',
        'has_header',
        'delimiter',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'has_header', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('CSV Configuration', {
            'fields': ['has_header', 'delimiter']
        }),
        ('Content', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "Content Preview"


@admin.register(D2Diagram)
class D2DiagramAdmin(admin.ModelAdmin):
    """Admin interface for D2 Diagram documents."""
    list_display = ['name', 'organization', 'diagram_type', 'content_preview', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'diagram_type']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Diagram Type', {
            'fields': ['diagram_type']
        }),
        ('D2 Content', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "D2 Content Preview"


@admin.register(ReactFlowDiagram)
class ReactFlowDiagramAdmin(admin.ModelAdmin):
    """Admin interface for React Flow Diagram documents."""
    list_display = [
        'name',
        'organization',
        'diagram_type',
        'react_flow_version',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'diagram_type']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Diagram Configuration', {
            'fields': ['diagram_type', 'react_flow_version']
        }),
        ('React Flow Content (JSON)', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "React Flow Content Preview"


@admin.register(MermaidDiagram)
class MermaidDiagramAdmin(admin.ModelAdmin):
    """Admin interface for Mermaid Diagram documents."""
    list_display = [
        'name',
        'organization',
        'diagram_type',
        'mermaid_version',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'diagram_type']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Diagram Configuration', {
            'fields': ['diagram_type', 'mermaid_version']
        }),
        ('Mermaid Content', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "Mermaid Content Preview"


@admin.register(ExcalidrawDiagram)
class ExcalidrawDiagramAdmin(admin.ModelAdmin):
    """Admin interface for Excalidraw Diagram documents."""
    list_display = [
        'name',
        'organization',
        'diagram_type',
        'excalidraw_version',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at', 'diagram_type']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Diagram Configuration', {
            'fields': ['diagram_type', 'excalidraw_version']
        }),
        ('Excalidraw Content (JSON)', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "Excalidraw Content Preview"


@admin.register(JSONCanvas)
class JSONCanvasAdmin(admin.ModelAdmin):
    """Admin interface for JSON Canvas documents."""
    list_display = [
        'name',
        'organization',
        'canvas_version',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'name', 'description']
        }),
        ('Canvas Configuration', {
            'fields': ['canvas_version']
        }),
        ('JSON Canvas Content', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "JSON Canvas Content Preview"


@admin.register(YooptaDocument)
class YooptaDocumentAdmin(admin.ModelAdmin):
    """Admin interface for Yoopta rich text documents."""
    list_display = [
        'name',
        'organization',
        'yoopta_version',
        'content_preview',
        'created_at'
    ]
    list_filter = ['organization', 'yoopta_version', 'created_at']
    search_fields = ['name', 'description', 'content', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['collections']

    fieldsets = [
        ('Basic Information', {
            'fields': ['organization', 'project', 'workspace', 'folder', 'name', 'description']
        }),
        ('Yoopta Configuration', {
            'fields': ['yoopta_version']
        }),
        ('Content (JSON)', {
            'fields': ['content']
        }),
        ('Metadata', {
            'fields': ['file_size', 'collections', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]

    def content_preview(self, obj):
        """Display first 50 characters of content."""
        if obj.content:
            return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
        return '-'
    content_preview.short_description = "Content Preview"


@admin.register(DocumentPreview)
class DocumentPreviewAdmin(admin.ModelAdmin):
    """Admin interface for document previews."""

    list_display = [
        'id',
        'document',
        'preview_kind',
        'status',
        'generated_at',
        'content_hash',
    ]
    list_filter = ['preview_kind', 'status', 'organization']
    search_fields = ['document__name', 'content_hash']
    readonly_fields = [
        'generated_at',
        'created_at',
        'updated_at',
        'error_message',
        'content_hash',
        'target_hash',
        'metadata',
    ]


class DocumentCollectionItemInline(admin.TabularInline):
    """Inline admin for DocumentCollectionItem within DocumentCollection."""
    model = DocumentCollectionItem
    extra = 0
    readonly_fields = ['created_at', 'updated_at', 'content_type', 'object_id']
    raw_id_fields = ['added_by', 'virtual_node']
    fields = [
        'position',
        'direction_added',
        'is_pinned',
        'content_type',
        'object_id',
        'virtual_node',
        'source_channel',
        'added_by',
        'created_at',
    ]


@admin.register(DocumentCollection)
class DocumentCollectionAdmin(admin.ModelAdmin):
    """
    Admin interface for DocumentCollection management.

    Supports all collection types: Artifact, Attachment, and Notebook.
    """
    list_display = [
        'name',
        'collection_type',
        'organization',
        'workspace',
        'owner',
        'is_active',
        'item_count',
        'created_by',
        'created_at',
    ]
    list_filter = [
        'collection_type',
        'is_active',
        'is_recent',
        'organization',
        'workspace',
        'created_at',
    ]
    search_fields = [
        'name',
        'description',
        'organization__name',
        'workspace__name',
        'owner__username',
        'owner__email',
    ]
    readonly_fields = ['created_at', 'updated_at', 'activated_at', 'sequence_head', 'sequence_tail']
    raw_id_fields = ['organization', 'project', 'workspace', 'owner', 'created_by']
    inlines = [DocumentCollectionItemInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ['name', 'description', 'collection_type']
        }),
        ('Scope', {
            'fields': ['organization', 'project', 'workspace', 'owner']
        }),
        ('Status', {
            'fields': ['is_active', 'is_recent', 'activated_at'],
            'classes': ['collapse'],
        }),
        ('Ordering', {
            'fields': ['sequence_head', 'sequence_tail'],
            'classes': ['collapse'],
        }),
        ('Metadata', {
            'fields': ['metadata', 'created_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def item_count(self, obj):
        """Display number of items in this collection."""
        return obj.items.count()
    item_count.short_description = "Items"

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'organization',
            'project',
            'workspace',
            'owner',
            'created_by',
        ).prefetch_related('items')


@admin.register(DocumentCollectionItem)
class DocumentCollectionItemAdmin(admin.ModelAdmin):
    """
    Admin interface for DocumentCollectionItem.

    Allows direct management of collection items with GenericForeignKey support.
    """
    list_display = [
        'id',
        'collection',
        'position',
        'content_type',
        'object_id',
        'source_channel',
        'is_pinned',
        'added_by',
        'created_at',
    ]
    list_filter = [
        'source_channel',
        'is_pinned',
        'direction_added',
        'content_type',
        'created_at',
    ]
    search_fields = [
        'collection__name',
        'object_id',
        'source_metadata',
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['collection', 'added_by', 'content_type', 'virtual_node']

    fieldsets = [
        ('Collection', {
            'fields': ['collection', 'position', 'direction_added', 'is_pinned']
        }),
        ('Content Reference', {
            'fields': ['content_type', 'object_id', 'virtual_node']
        }),
        ('Source', {
            'fields': ['source_channel', 'source_metadata']
        }),
        ('Preview', {
            'fields': ['preview'],
            'classes': ['collapse'],
        }),
        ('Metadata', {
            'fields': ['added_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'collection',
            'collection__organization',
            'collection__workspace',
            'content_type',
            'added_by',
            'virtual_node',
        )


@admin.register(VirtualCollectionNode)
class VirtualCollectionNodeAdmin(admin.ModelAdmin):
    """
    Admin interface for VirtualCollectionNode.

    Manages transient/virtual items before they are materialized into documents.
    """
    list_display = [
        'id',
        'node_type',
        'workspace',
        'preview_text_truncated',
        'is_materialized',
        'expires_at',
        'created_by',
        'created_at',
    ]
    list_filter = [
        'node_type',
        'workspace',
        'materialized_content_type',
        'created_at',
        'expires_at',
    ]
    search_fields = [
        'node_type',
        'preview_text',
        'origin_reference',
        'workspace__name',
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['workspace', 'created_by', 'materialized_content_type']

    fieldsets = [
        ('Basic Information', {
            'fields': ['workspace', 'node_type', 'origin_reference']
        }),
        ('Content', {
            'fields': ['payload', 'preview_text', 'preview_image']
        }),
        ('Materialization', {
            'fields': ['materialized_content_type', 'materialized_object_id'],
            'classes': ['collapse'],
        }),
        ('Lifecycle', {
            'fields': ['expires_at'],
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def preview_text_truncated(self, obj):
        """Display first 50 characters of preview text."""
        if obj.preview_text:
            return obj.preview_text[:50] + ('...' if len(obj.preview_text) > 50 else '')
        return '-'
    preview_text_truncated.short_description = "Preview"

    def is_materialized(self, obj):
        """Check if node has been materialized to a document."""
        return bool(obj.materialized_content_type and obj.materialized_object_id)
    is_materialized.boolean = True
    is_materialized.short_description = "Materialized"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'workspace',
            'created_by',
            'materialized_content_type',
        )
