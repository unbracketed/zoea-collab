"""
Document models with multi-table inheritance hierarchy.

This module implements a hierarchical document model structure:
- Document (base)
  - Image
  - PDF
  - FileDocument
  - TextDocument
    - Markdown
    - CSV
    - JSONCanvas
    - YooptaDocument
    - Diagram (abstract intermediate)
      - D2Diagram
      - ReactFlowDiagram
      - MermaidDiagram
      - ExcalidrawDiagram
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from model_utils.managers import InheritanceQuerySetMixin
from mptt.models import MPTTModel, TreeForeignKey

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()


class DocumentQuerySet(InheritanceQuerySetMixin, OrganizationScopedQuerySet):
    """
    Combined queryset for organization scoping and efficient inheritance queries.

    This queryset provides:
    - Organization-scoped filtering (.for_user(), .for_organization())
    - Efficient polymorphic queries (.select_subclasses())
    - Active document filtering (.active()) to exclude trashed documents
    """

    def active(self):
        """Filter to non-trashed documents only."""
        return self.filter(is_trashed=False)

    def trashed(self):
        """Filter to trashed documents only."""
        return self.filter(is_trashed=True)


class FolderQuerySet(OrganizationScopedQuerySet):
    """Organization-scoped queryset for folders."""

    def for_project(self, project):
        return self.filter(project=project)


class Folder(MPTTModel):
    """Hierarchical folder structure for organizing documents."""

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='folders',
        help_text="Organization that owns this folder"
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='folders',
        help_text="Project that owns this folder"
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent folder"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False,
        help_text="System/hidden folder (excluded from normal listings)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_folders',
    )

    objects = FolderQuerySet.as_manager()

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name = "Folder"
        verbose_name_plural = "Folders"
        unique_together = [['project', 'parent', 'name']]
        indexes = [
            models.Index(fields=['project', 'parent', 'name']),
            models.Index(fields=['is_system']),
        ]

    def __str__(self):
        return self.get_path()

    def clean(self):
        super().clean()
        if self.parent:
            if self.parent.project_id != self.project_id:
                raise ValidationError("Folder must share the same project as its parent")

    def save(self, *args, **kwargs):
        # Align organization with project automatically
        if self.parent:
            self.project = self.parent.project
            self.organization = self.parent.organization
        elif self.project:
            self.organization = self.project.organization
        super().save(*args, **kwargs)

    def get_path(self):
        ancestors = self.get_ancestors(include_self=True)
        return "/".join(folder.name for folder in ancestors)

    def list_children(self):
        return self.get_children()

    def list_documents(self):
        return self.documents.all()


class Collection(models.Model):
    """
    DEPRECATED: Use DocumentCollection instead.

    Legacy collection of documents scoped to a project.
    Kept for backward compatibility during migration.
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='legacy_collections',
        help_text="The organization that owns this collection"
    )

    # Project relationship
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='legacy_collections',
        null=True,
        blank=True,
        help_text="The project this collection belongs to"
    )

    # Required fields
    name = models.CharField(
        max_length=255,
        help_text="Collection name"
    )

    # Optional fields
    description = models.TextField(
        blank=True,
        help_text="Collection description"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_legacy_collections',
        help_text="User who created this collection"
    )

    # Use organization-scoped queryset manager
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        verbose_name = "Collection (Legacy)"
        verbose_name_plural = "Collections (Legacy)"
        ordering = ['-created_at']
        unique_together = [['project', 'name']]
        indexes = [
            models.Index(fields=['project', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


# =============================================================================
# Document Collection System
# =============================================================================


class CollectionType(models.TextChoices):
    """Types of document collections."""

    ARTIFACT = "artifact", "Artifact"
    ATTACHMENT = "attachment", "Attachment"
    NOTEBOOK = "notebook", "Notebook"


class CollectionItemDirection(models.TextChoices):
    """Direction for deque-style item insertion."""

    LEFT = "left", "Left"
    RIGHT = "right", "Right"


class CollectionItemSourceChannel(models.TextChoices):
    """High-level origin hint for collection items."""

    CONVERSATION = "conversation", "Conversation"
    MESSAGE = "message", "Message"
    DOCUMENT = "document", "Document"
    WORKFLOW = "workflow", "Workflow"
    CANVAS = "canvas", "Canvas"
    CODE = "code", "Code Snippet"
    TOOL = "tool", "Tool Output"
    EMAIL = "email", "Email"
    UNKNOWN = "unknown", "Unknown"


class DocumentCollectionQuerySet(OrganizationScopedQuerySet):
    """Custom queryset with convenience filters for document collections."""

    def for_project(self, project):
        """Filter by project."""
        return self.filter(project=project)

    def for_owner(self, owner):
        """Filter by owner (for notebooks)."""
        return self.filter(owner=owner)

    def active(self):
        """Filter to active collections only."""
        return self.filter(is_active=True)

    def notebooks(self):
        """Filter to notebook collections only."""
        return self.filter(collection_type=CollectionType.NOTEBOOK)

    def artifacts(self):
        """Filter to artifact collections only."""
        return self.filter(collection_type=CollectionType.ARTIFACT)

    def attachments(self):
        """Filter to attachment collections only."""
        return self.filter(collection_type=CollectionType.ATTACHMENT)


class DocumentCollection(models.Model):
    """
    Unified collection model for artifacts, attachments, and notebooks.

    Combines features from the legacy Collection model and Clipboard model:
    - Multi-tenant scoping (organization, project)
    - Collection types: ARTIFACT, ATTACHMENT, NOTEBOOK
    - Deque-style ordering for items (sequence_head/tail)
    - Active/recent status for notebooks
    - Owner field for user-specific notebooks

    Usage:
        # Create an artifacts collection for a conversation
        collection = DocumentCollection.objects.create(
            organization=org,
            project=project,
            collection_type=CollectionType.ARTIFACT,
            name="Conversation Artifacts",
        )

        # Create a notebook for a user
        notebook = DocumentCollection.objects.create(
            organization=org,
            project=project,
            collection_type=CollectionType.NOTEBOOK,
            owner=user,
            name="My Notebook",
            is_active=True,
        )
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='document_collections',
        help_text="The organization that owns this collection"
    )

    # Project relationship
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='document_collections',
        null=True,
        blank=True,
        help_text="The project this collection belongs to"
    )

    # Collection type
    collection_type = models.CharField(
        max_length=20,
        choices=CollectionType.choices,
        default=CollectionType.ARTIFACT,
        help_text="Type of collection (artifact, attachment, or notebook)"
    )

    # Owner (for notebooks - user who owns this collection)
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='owned_document_collections',
        help_text="User who owns this collection (for notebooks)"
    )

    # Basic fields
    name = models.CharField(
        max_length=255,
        help_text="Collection name"
    )
    description = models.TextField(
        blank=True,
        help_text="Collection description"
    )

    # Status flags (primarily for notebooks)
    is_active = models.BooleanField(
        default=False,
        help_text="Whether this is the active collection (for notebooks)"
    )
    is_recent = models.BooleanField(
        default=False,
        help_text="Whether this collection is in the recent list (for notebooks)"
    )
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this collection was last activated"
    )

    # Deque-style ordering for items
    sequence_head = models.BigIntegerField(
        default=0,
        help_text="Tracks the head index for deque-style item insertion"
    )
    sequence_tail = models.BigIntegerField(
        default=-1,
        help_text="Tracks the tail index for deque-style item insertion"
    )

    # Flexible metadata storage
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary metadata (e.g., notepad content for notebooks)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_document_collections',
        help_text="User who created this collection"
    )

    objects = DocumentCollectionQuerySet.as_manager()

    class Meta:
        verbose_name = "Document Collection"
        verbose_name_plural = "Document Collections"
        ordering = ['-activated_at', '-updated_at']
        indexes = [
            models.Index(fields=['project', 'collection_type']),
            models.Index(fields=['project', 'owner']),
            models.Index(fields=['collection_type', '-created_at']),
        ]
        constraints = [
            # Only one active notebook per user per project
            models.UniqueConstraint(
                condition=models.Q(is_active=True, collection_type='notebook'),
                fields=['project', 'owner'],
                name='unique_active_notebook_per_user',
            )
        ]

    def __str__(self):
        type_label = self.get_collection_type_display()
        return f"{self.name} ({type_label})"

    def activate(self):
        """Mark this collection as active (for notebooks)."""
        from django.utils import timezone
        self.is_active = True
        self.is_recent = False
        self.activated_at = timezone.now()

    def deactivate(self):
        """Mark this collection as inactive (for notebooks)."""
        self.is_active = False
        self.is_recent = True

    def reserve_position(self, direction: str) -> int:
        """
        Reserve the next available position for item insertion.

        Args:
            direction: 'left' or 'right' indicating insertion direction.

        Returns:
            The reserved position value.
        """
        if direction == CollectionItemDirection.LEFT:
            self.sequence_head -= 1
            return self.sequence_head
        self.sequence_tail += 1
        return self.sequence_tail

    def save(self, *args, **kwargs):
        # Auto-populate organization from project
        if self.project and not self.organization:
            self.organization = self.project.organization
        super().save(*args, **kwargs)


class DocumentCollectionItem(models.Model):
    """
    Represents a single entry in a document collection.

    Supports both persisted documents (via GenericForeignKey) and transient
    virtual nodes for items that haven't been saved as documents yet.

    Features:
    - GenericForeignKey to reference any model (Document subclasses, etc.)
    - Position-based ordering for deque-style operations
    - Source tracking to identify where the item came from
    - Preview data for UI rendering
    - Pinning support
    """

    collection = models.ForeignKey(
        DocumentCollection,
        on_delete=models.CASCADE,
        related_name='items',
        help_text="The collection this item belongs to"
    )

    # Position for ordering (supports deque semantics)
    position = models.BigIntegerField(
        help_text="Relative ordering value supporting deque semantics"
    )
    direction_added = models.CharField(
        max_length=5,
        choices=CollectionItemDirection.choices,
        default=CollectionItemDirection.RIGHT,
        help_text="Direction this item was added (left or right)"
    )

    # User who added the item
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='added_collection_items',
        help_text="User who added this item"
    )

    # Pinning
    is_pinned = models.BooleanField(
        default=False,
        help_text="Whether this item is pinned"
    )

    # Generic foreign key to reference any content
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Content type of the referenced object"
    )
    object_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID of the referenced object"
    )

    # Virtual node reference for transient items
    virtual_node = models.ForeignKey(
        'VirtualCollectionNode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_items',
        help_text="Reference to a virtual node for transient items"
    )

    # Source tracking
    source_channel = models.CharField(
        max_length=32,
        choices=CollectionItemSourceChannel.choices,
        default=CollectionItemSourceChannel.UNKNOWN,
        help_text="High-level origin hint for this item"
    )
    source_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the source"
    )

    # Preview data for UI
    preview = models.JSONField(
        null=True,
        blank=True,
        help_text="Custom preview data (e.g., chat bubble, diagram thumbnail)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Collection Item"
        verbose_name_plural = "Collection Items"
        ordering = ['position', '-created_at']
        indexes = [
            models.Index(fields=['collection', 'position']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"CollectionItem({self.collection_id}, pos={self.position})"

    @property
    def content_object(self):
        """Get the referenced content object via generic foreign key."""
        if self.content_type_id and self.object_id:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_id(self.content_type_id)
            return ct.get_object_for_this_type(pk=self.object_id)
        return None

    @content_object.setter
    def content_object(self, obj):
        """Set the content object via generic foreign key."""
        if obj is None:
            self.content_type = None
            self.object_id = None
        else:
            from django.contrib.contenttypes.models import ContentType
            self.content_type = ContentType.objects.get_for_model(obj)
            self.object_id = str(obj.pk)


class VirtualCollectionNode(models.Model):
    """
    Stores transient project artifacts that may later be persisted.

    Virtual nodes hold temporary data (code snippets, chat excerpts, etc.)
    that can be added to collections before being saved as proper documents.
    They can be materialized into actual documents when needed.

    Features:
    - Project-scoped for proper isolation
    - TTL support via expires_at for automatic cleanup
    - Materialization tracking to link to persisted documents
    - Flexible payload storage for any content type
    """

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='virtual_collection_nodes',
        null=True,
        blank=True,
        help_text="Project this node belongs to"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='virtual_collection_nodes',
        help_text="User who created this node"
    )

    # Node type and content
    node_type = models.CharField(
        max_length=64,
        help_text="Type identifier for the node content"
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary node data"
    )

    # Preview data
    preview_text = models.TextField(
        blank=True,
        help_text="Text preview for UI display"
    )
    preview_image = models.URLField(
        blank=True,
        help_text="Image preview URL"
    )

    # Origin tracking
    origin_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reference to the origin of this node"
    )

    # TTL for automatic cleanup
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this node expires (for automatic cleanup)"
    )

    # Materialization tracking
    materialized_content_type = models.ForeignKey(
        'contenttypes.ContentType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='materialized_virtual_collection_nodes',
        help_text="Content type of the materialized object"
    )
    materialized_object_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID of the materialized object"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Virtual Collection Node"
        verbose_name_plural = "Virtual Collection Nodes"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['project', 'node_type']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"VirtualNode({self.node_type})"

    def is_expired(self) -> bool:
        """Return True if the node has passed its TTL."""
        from django.utils import timezone
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def materialized_object(self):
        """Get the materialized content object."""
        if self.materialized_content_type_id and self.materialized_object_id:
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_id(self.materialized_content_type_id)
            return ct.get_object_for_this_type(pk=self.materialized_object_id)
        return None


class Document(models.Model):
    """
    Base document model with multi-table inheritance.

    All document types inherit from this base class. Documents are scoped to
    a project. Use select_subclasses() to efficiently query all
    document types in a single query:

        documents = Document.objects.select_subclasses()
        for doc in documents:
            if isinstance(doc, Image):
                print(doc.image_file.url)
    """

    # Organization relationship (required for multi-tenancy)
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='documents',
        help_text="The organization that owns this document"
    )

    # Project relationship
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True,
        help_text="The project this document belongs to"
    )

    # Required fields
    name = models.CharField(
        max_length=255,
        help_text="Document name"
    )

    # Optional fields
    description = models.TextField(
        blank=True,
        help_text="Document description"
    )

    # Relationships
    collections = models.ManyToManyField(
        Collection,
        blank=True,
        related_name='documents',
        help_text="Collections this document belongs to"
    )
    folder = TreeForeignKey(
        'documents.Folder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
        help_text="Folder containing this document"
    )

    # Metadata
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )

    # Gemini File Search integration
    gemini_file_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Gemini File Search file ID for this document"
    )
    gemini_synced_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time this document was synced to Gemini File Search"
    )
    gemini_sync_error = models.TextField(
        blank=True,
        null=True,
        help_text="Error message from last failed sync attempt"
    )
    gemini_sync_attempts = models.IntegerField(
        default=0,
        help_text="Number of sync attempts (for retry tracking)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_documents',
        help_text="User who created this document"
    )

    # Trash fields for soft-delete
    is_trashed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this document is in the trash"
    )
    trashed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this document was moved to trash"
    )
    original_folder_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Original folder ID before trashing (for restore)"
    )

    # Combined manager for organization scoping and inheritance
    objects = DocumentQuerySet.as_manager()

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['folder']),
        ]

    def __str__(self):
        return self.name

    def get_type_name(self):
        """Return the specific document type name."""
        return self.__class__.__name__

    def move_to_trash(self):
        """Move document to trash, preserving original folder for potential restore."""
        from django.utils import timezone
        self.original_folder_id = self.folder_id
        self.folder = None
        self.is_trashed = True
        self.trashed_at = timezone.now()
        self.save(update_fields=['folder', 'is_trashed', 'trashed_at', 'original_folder_id', 'updated_at'])

    def restore_from_trash(self, target_folder_id=None):
        """
        Restore document from trash.

        Args:
            target_folder_id: Optional folder ID to restore to. If not provided,
                            restores to original folder if it still exists.
        """
        from documents.models import Folder
        folder_id = target_folder_id or self.original_folder_id
        if folder_id:
            # Verify folder still exists before restoring to it
            if Folder.objects.filter(id=folder_id).exists():
                self.folder_id = folder_id
            else:
                self.folder = None
        else:
            self.folder = None
        self.is_trashed = False
        self.trashed_at = None
        self.original_folder_id = None
        self.save(update_fields=['folder', 'is_trashed', 'trashed_at', 'original_folder_id', 'updated_at'])

    def save(self, *args, **kwargs):
        if self.folder:
            if self.project and self.folder.project_id != self.project_id:
                raise ValidationError("Document folder must belong to the same project")
            self.project = self.folder.project
            self.organization = self.folder.organization
        super().save(*args, **kwargs)


class Image(Document):
    """
    Image document type.

    Supports common image formats (JPEG, PNG, GIF, etc.).
    """

    image_file = models.ImageField(
        upload_to='images/%Y/%m/%d/',
        help_text="Image file"
    )

    # Optional image metadata (auto-populated by ImageField)
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
        help_text="Image width in pixels"
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
        help_text="Image height in pixels"
    )

    class Meta:
        verbose_name = "Image"
        verbose_name_plural = "Images"

    def save(self, *args, **kwargs):
        """Auto-populate width and height from image file."""
        if self.image_file:
            self.width = self.image_file.width
            self.height = self.image_file.height
        super().save(*args, **kwargs)


class ImageCaption(models.Model):
    """
    LLM-generated caption for an image document.
    """

    image = models.ForeignKey(
        Image,
        on_delete=models.CASCADE,
        related_name="captions",
        help_text="Image document this caption describes",
    )
    provider = models.CharField(
        max_length=50,
        help_text="LLM provider used for the caption (openai, gemini, etc.)",
    )
    model = models.CharField(
        max_length=100,
        help_text="Model identifier used for the caption",
    )
    caption = models.TextField(
        help_text="Generated caption text",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Image Caption"
        verbose_name_plural = "Image Captions"
        unique_together = [["image", "provider", "model"]]
        indexes = [
            models.Index(fields=["image", "provider", "model"]),
        ]

    def __str__(self):
        return f"Caption for Image {self.image_id} ({self.provider}/{self.model})"


class PDF(Document):
    """
    PDF document type.

    Supports PDF files for reports, documentation, etc.
    """

    pdf_file = models.FileField(
        upload_to='pdfs/%Y/%m/%d/',
        help_text="PDF file"
    )

    page_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of pages in the PDF"
    )

    class Meta:
        verbose_name = "PDF Document"
        verbose_name_plural = "PDF Documents"

    def save(self, *args, **kwargs):
        """Auto-populate page_count and file_size from PDF file."""
        if self.pdf_file:
            # Set file_size if not already set
            if not self.file_size:
                self.file_size = getattr(self.pdf_file, "size", None)

            # Extract page count if not already set
            if not self.page_count:
                try:
                    import fitz  # PyMuPDF

                    self.pdf_file.seek(0)
                    pdf_bytes = self.pdf_file.read()
                    self.pdf_file.seek(0)  # Reset for Django to save

                    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                        self.page_count = len(doc)
                except Exception:
                    pass  # Fail gracefully if PDF is malformed

        super().save(*args, **kwargs)

    def get_text_content(self) -> str:
        """
        Extract plain text from PDF for search indexing.

        Extracts text from all pages, suitable for Gemini File Search.

        Returns:
            str: Plain text content from all PDF pages.
        """
        if not self.pdf_file:
            return ""

        try:
            import fitz  # PyMuPDF

            self.pdf_file.open("rb")
            try:
                pdf_bytes = self.pdf_file.read()
                with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text())
                    return "\n\n".join(text_parts)
            finally:
                self.pdf_file.close()
        except Exception:
            return ""


class WordDocument(Document):
    """
    Word document type (.docx).

    Supports Microsoft Word documents for viewing and text extraction.
    """

    docx_file = models.FileField(
        upload_to='docx/%Y/%m/%d/',
        help_text="Word document file (.docx)"
    )

    paragraph_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of paragraphs in the document"
    )

    class Meta:
        verbose_name = "Word Document"
        verbose_name_plural = "Word Documents"

    def save(self, *args, **kwargs):
        """Auto-populate paragraph_count and file_size from docx file."""
        if self.docx_file:
            # Set file_size if not already set
            if not self.file_size:
                self.file_size = getattr(self.docx_file, "size", None)

            # Extract paragraph count if not already set
            if not self.paragraph_count:
                try:
                    from docx import Document as DocxDocument

                    self.docx_file.seek(0)
                    doc = DocxDocument(self.docx_file)
                    self.docx_file.seek(0)  # Reset for Django to save
                    self.paragraph_count = len(doc.paragraphs)
                except Exception:
                    pass  # Fail gracefully if document is malformed

        super().save(*args, **kwargs)

    def get_text_content(self) -> str:
        """
        Extract plain text from Word document for search indexing.

        Returns:
            str: Plain text content from all paragraphs.
        """
        if not self.docx_file:
            return ""

        try:
            from docx import Document as DocxDocument

            self.docx_file.open("rb")
            try:
                doc = DocxDocument(self.docx_file)
                text_parts = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        text_parts.append(para.text)
                # Also extract text from tables
                for table in doc.tables:
                    for row in table.rows:
                        row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_text:
                            text_parts.append(" | ".join(row_text))
                return "\n\n".join(text_parts)
            finally:
                self.docx_file.close()
        except Exception:
            return ""

    def get_html_content(self) -> str:
        """
        Convert Word document to HTML for viewing.

        Returns:
            str: HTML representation of the document.
        """
        if not self.docx_file:
            return ""

        try:
            from docx import Document as DocxDocument

            self.docx_file.open("rb")
            try:
                doc = DocxDocument(self.docx_file)
                html_parts = ['<div class="docx-content">']

                for para in doc.paragraphs:
                    if not para.text.strip():
                        continue

                    # Determine heading level from style
                    style_name = para.style.name if para.style else ""
                    if style_name.startswith("Heading 1"):
                        html_parts.append(f"<h1>{self._escape_html(para.text)}</h1>")
                    elif style_name.startswith("Heading 2"):
                        html_parts.append(f"<h2>{self._escape_html(para.text)}</h2>")
                    elif style_name.startswith("Heading 3"):
                        html_parts.append(f"<h3>{self._escape_html(para.text)}</h3>")
                    elif style_name.startswith("Heading"):
                        html_parts.append(f"<h4>{self._escape_html(para.text)}</h4>")
                    else:
                        # Regular paragraph with inline formatting
                        para_html = self._paragraph_to_html(para)
                        html_parts.append(f"<p>{para_html}</p>")

                # Convert tables
                for table in doc.tables:
                    html_parts.append("<table>")
                    for i, row in enumerate(table.rows):
                        html_parts.append("<tr>")
                        tag = "th" if i == 0 else "td"
                        for cell in row.cells:
                            html_parts.append(f"<{tag}>{self._escape_html(cell.text)}</{tag}>")
                        html_parts.append("</tr>")
                    html_parts.append("</table>")

                html_parts.append("</div>")
                return "\n".join(html_parts)
            finally:
                self.docx_file.close()
        except Exception:
            return "<p>Error rendering document</p>"

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _paragraph_to_html(self, para) -> str:
        """Convert paragraph with inline formatting to HTML."""
        html_parts = []
        for run in para.runs:
            text = self._escape_html(run.text)
            if run.bold:
                text = f"<strong>{text}</strong>"
            if run.italic:
                text = f"<em>{text}</em>"
            if run.underline:
                text = f"<u>{text}</u>"
            html_parts.append(text)
        return "".join(html_parts)


class SpreadsheetDocument(Document):
    """
    Spreadsheet document type (.xlsx).

    Supports Microsoft Excel spreadsheets for viewing and data extraction.
    """

    xlsx_file = models.FileField(
        upload_to='xlsx/%Y/%m/%d/',
        help_text="Excel spreadsheet file (.xlsx)"
    )

    sheet_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of sheets in the spreadsheet"
    )

    class Meta:
        verbose_name = "Spreadsheet Document"
        verbose_name_plural = "Spreadsheet Documents"

    def save(self, *args, **kwargs):
        """Auto-populate sheet_count and file_size from xlsx file."""
        if self.xlsx_file:
            # Set file_size if not already set
            if not self.file_size:
                self.file_size = getattr(self.xlsx_file, "size", None)

            # Extract sheet count if not already set
            if not self.sheet_count:
                try:
                    from openpyxl import load_workbook

                    self.xlsx_file.seek(0)
                    wb = load_workbook(self.xlsx_file, read_only=True)
                    self.xlsx_file.seek(0)  # Reset for Django to save
                    self.sheet_count = len(wb.sheetnames)
                    wb.close()
                except Exception:
                    pass  # Fail gracefully if spreadsheet is malformed

        super().save(*args, **kwargs)

    def get_text_content(self) -> str:
        """
        Extract plain text from spreadsheet for search indexing.

        Returns:
            str: Plain text content from all cells.
        """
        if not self.xlsx_file:
            return ""

        try:
            from openpyxl import load_workbook

            self.xlsx_file.open("rb")
            try:
                wb = load_workbook(self.xlsx_file, read_only=True, data_only=True)
                text_parts = []

                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    text_parts.append(f"Sheet: {sheet_name}")
                    for row in sheet.iter_rows():
                        row_values = [
                            str(cell.value) for cell in row
                            if cell.value is not None
                        ]
                        if row_values:
                            text_parts.append(" | ".join(row_values))

                wb.close()
                return "\n".join(text_parts)
            finally:
                self.xlsx_file.close()
        except Exception:
            return ""

    def get_html_content(self) -> str:
        """
        Convert spreadsheet to HTML tables for viewing.

        Returns:
            str: HTML representation with one table per sheet.
        """
        if not self.xlsx_file:
            return ""

        try:
            from openpyxl import load_workbook

            self.xlsx_file.open("rb")
            try:
                wb = load_workbook(self.xlsx_file, read_only=True, data_only=True)
                html_parts = ['<div class="xlsx-content">']

                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    html_parts.append('<div class="xlsx-sheet">')
                    html_parts.append(f"<h3>{self._escape_html(sheet_name)}</h3>")
                    html_parts.append('<div class="table-wrapper"><table>')

                    for i, row in enumerate(sheet.iter_rows()):
                        html_parts.append("<tr>")
                        tag = "th" if i == 0 else "td"
                        for cell in row:
                            value = str(cell.value) if cell.value is not None else ""
                            html_parts.append(f"<{tag}>{self._escape_html(value)}</{tag}>")
                        html_parts.append("</tr>")

                    html_parts.append("</table></div></div>")

                wb.close()
                html_parts.append("</div>")
                return "\n".join(html_parts)
            finally:
                self.xlsx_file.close()
        except Exception:
            return "<p>Error rendering spreadsheet</p>"

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


class FileDocument(Document):
    """
    Generic file-based document type.

    Used for attachments or arbitrary uploaded files that are not handled by a
    more specific document subclass.
    """

    file = models.FileField(
        upload_to='files/%Y/%m/%d/',
        help_text="Uploaded file"
    )
    original_filename = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Original filename from the source"
    )
    content_type = models.CharField(
        max_length=255,
        blank=True,
        help_text="MIME type of the file"
    )

    class Meta:
        verbose_name = "File Document"
        verbose_name_plural = "File Documents"

    def save(self, *args, **kwargs):
        if self.file:
            # Update file size and default name from uploaded file
            self.file_size = getattr(self.file, "size", self.file_size)
            if not self.name:
                self.name = self.original_filename or self.file.name
        super().save(*args, **kwargs)


class TextDocument(Document):
    """
    Intermediate base class for text-based documents.

    Provides a content field for storing text data.
    All text-based document types inherit from this class.
    """

    content = models.TextField(
        blank=True,
        help_text="Text content of the document"
    )

    class Meta:
        verbose_name = "Text Document"
        verbose_name_plural = "Text Documents"


class Markdown(TextDocument):
    """
    Markdown document type.

    Stores Markdown-formatted text content.
    """

    class Meta:
        verbose_name = "Markdown Document"
        verbose_name_plural = "Markdown Documents"


class CSV(TextDocument):
    """
    CSV document type.

    Stores CSV data with optional metadata about structure.
    """

    has_header = models.BooleanField(
        default=True,
        help_text="Whether the CSV has a header row"
    )

    delimiter = models.CharField(
        max_length=5,
        default=',',
        help_text="Delimiter character (e.g., ',' or ';')"
    )

    class Meta:
        verbose_name = "CSV Document"
        verbose_name_plural = "CSV Documents"


class JSONCanvas(TextDocument):
    """
    JSON Canvas document type.

    Stores JSON Canvas format data for spatial canvas layouts.
    Used by tools like Obsidian Canvas for node-based visual layouts.
    """

    canvas_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="JSON Canvas format version"
    )

    class Meta:
        verbose_name = "JSON Canvas"
        verbose_name_plural = "JSON Canvases"


class Diagram(TextDocument):
    """
    Abstract intermediate base for diagram documents.

    Provides common functionality for all diagram types.
    Not instantiated directly - use D2Diagram, ReactFlowDiagram, or MermaidDiagram.
    """

    DIAGRAM_TYPE_CHOICES = [
        ('d2', 'D2 Diagram'),
        ('react_flow', 'React Flow Diagram'),
        ('mermaid', 'Mermaid Diagram'),
        ('excalidraw', 'Excalidraw Diagram'),
    ]

    diagram_type = models.CharField(
        max_length=20,
        choices=DIAGRAM_TYPE_CHOICES,
        help_text="Type of diagram"
    )

    class Meta:
        abstract = True


class D2Diagram(Diagram):
    """
    D2 diagram document type.

    Stores D2 diagram language content for rendering concept maps.
    """

    def save(self, *args, **kwargs):
        """Ensure diagram_type is set to d2."""
        self.diagram_type = 'd2'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "D2 Diagram"
        verbose_name_plural = "D2 Diagrams"


class ReactFlowDiagram(Diagram):
    """
    React Flow diagram document type.

    Stores React Flow geometry data (JSON) for interactive diagrams.
    """

    react_flow_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="React Flow library version used"
    )

    def save(self, *args, **kwargs):
        """Ensure diagram_type is set to react_flow."""
        self.diagram_type = 'react_flow'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "React Flow Diagram"
        verbose_name_plural = "React Flow Diagrams"


class MermaidDiagram(Diagram):
    """
    Mermaid diagram document type.

    Stores Mermaid diagram syntax for flowcharts, sequence diagrams, gantt charts, etc.
    Mermaid is a JavaScript-based diagramming tool that renders markdown-inspired text.
    """

    mermaid_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Mermaid library version used"
    )

    def save(self, *args, **kwargs):
        """Ensure diagram_type is set to mermaid."""
        self.diagram_type = 'mermaid'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Mermaid Diagram"
        verbose_name_plural = "Mermaid Diagrams"


class ExcalidrawDiagram(Diagram):
    """
    Excalidraw diagram document type.

    Stores Excalidraw JSON data for freehand-style diagrams and sketches.
    Excalidraw is a virtual whiteboard tool for creating hand-drawn like diagrams.
    Content is stored in Excalidraw's native JSON format.

    See: https://docs.excalidraw.com/docs/codebase/json-schema
    """

    excalidraw_version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Excalidraw library version used"
    )

    def save(self, *args, **kwargs):
        """Ensure diagram_type is set to excalidraw."""
        self.diagram_type = 'excalidraw'
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Excalidraw Diagram"
        verbose_name_plural = "Excalidraw Diagrams"


class YooptaDocument(TextDocument):
    """
    Yoopta rich text document type.

    Stores Yoopta-Editor JSON content for block-based WYSIWYG editing.
    Yoopta is a Notion-like editor with plugins for headings, lists, code, images, etc.
    Content is stored as Yoopta's native JSON format in the inherited `content` field.

    See: https://yoopta.dev/
    """

    yoopta_version = models.CharField(
        max_length=20,
        default="4.0",
        help_text="Yoopta-Editor version used"
    )

    class Meta:
        verbose_name = "Yoopta Document"
        verbose_name_plural = "Yoopta Documents"

    def get_text_content(self) -> str:
        """
        Extract plain text from Yoopta JSON content for search indexing.

        Walks the Yoopta block structure and extracts text from all blocks,
        ordered by their meta.order property.

        Returns:
            str: Plain text content suitable for Gemini file search indexing.
        """
        import json

        if not self.content:
            return ""

        try:
            # Parse JSON content if it's a string
            if isinstance(self.content, str):
                content = json.loads(self.content)
            else:
                content = self.content

            if not isinstance(content, dict):
                return ""

            # Sort blocks by meta.order
            blocks = []
            for block_id, block_data in content.items():
                if not isinstance(block_data, dict):
                    continue
                order = block_data.get("meta", {}).get("order", 0)
                blocks.append((order, block_data))

            blocks.sort(key=lambda x: x[0])

            # Extract text from each block
            text_parts = []
            for _, block_data in blocks:
                block_text = self._extract_text_from_block(block_data)
                if block_text:
                    text_parts.append(block_text)

            return "\n\n".join(text_parts)

        except (json.JSONDecodeError, TypeError, KeyError):
            # If parsing fails, return raw content as fallback
            return self.content if isinstance(self.content, str) else ""

    def _extract_text_from_block(self, block_data: dict) -> str:
        """
        Extract text from a single Yoopta block.

        Args:
            block_data: A Yoopta block dictionary with 'value' containing elements.

        Returns:
            str: Extracted text from the block.
        """
        if not isinstance(block_data, dict):
            return ""

        value = block_data.get("value", [])
        if not isinstance(value, list):
            return ""

        text_parts = []
        for element in value:
            element_text = self._extract_text_from_element(element)
            if element_text:
                text_parts.append(element_text)

        return "\n".join(text_parts)

    def _extract_text_from_element(self, element: dict) -> str:
        """
        Recursively extract text from a Yoopta element.

        Args:
            element: A Yoopta element dictionary with 'children' or 'text'.

        Returns:
            str: Extracted text from the element and its children.
        """
        if not isinstance(element, dict):
            return ""

        # Direct text node
        if "text" in element:
            return element["text"]

        # Element with children
        children = element.get("children", [])
        if not isinstance(children, list):
            return ""

        text_parts = []
        for child in children:
            child_text = self._extract_text_from_element(child)
            if child_text:
                text_parts.append(child_text)

        return "".join(text_parts)

    def get_markdown_content(self) -> str:
        """
        Export Yoopta JSON content to Markdown format.

        Converts blocks to their Markdown equivalents:
        - Headings → # syntax
        - Paragraphs → plain text with blank lines
        - Lists → - or 1. prefixes
        - Code blocks → ``` fences
        - Blockquotes → > prefix
        - Links → [text](url) syntax

        Returns:
            str: Markdown representation of the document.
        """
        import json

        if not self.content:
            return ""

        try:
            if isinstance(self.content, str):
                content = json.loads(self.content)
            else:
                content = self.content

            if not isinstance(content, dict):
                return ""

            # Sort blocks by meta.order
            blocks = []
            for block_id, block_data in content.items():
                if not isinstance(block_data, dict):
                    continue
                order = block_data.get("meta", {}).get("order", 0)
                blocks.append((order, block_data))

            blocks.sort(key=lambda x: x[0])

            # Convert each block to markdown
            markdown_parts = []
            for _, block_data in blocks:
                block_md = self._block_to_markdown(block_data)
                if block_md:
                    markdown_parts.append(block_md)

            return "\n\n".join(markdown_parts)

        except (json.JSONDecodeError, TypeError, KeyError):
            return self.content if isinstance(self.content, str) else ""

    def _block_to_markdown(self, block_data: dict) -> str:
        """Convert a single Yoopta block to Markdown."""
        if not isinstance(block_data, dict):
            return ""

        block_type = block_data.get("type", "").lower()
        value = block_data.get("value", [])

        if not isinstance(value, list) or not value:
            return ""

        # Get the first element's type for more specific handling
        first_elem = value[0] if value else {}
        elem_type = first_elem.get("type", "").lower() if isinstance(first_elem, dict) else ""

        # Handle different block types
        if "heading" in block_type or "heading" in elem_type:
            level = 1
            if "one" in block_type or "one" in elem_type or "1" in elem_type:
                level = 1
            elif "two" in block_type or "two" in elem_type or "2" in elem_type:
                level = 2
            elif "three" in block_type or "three" in elem_type or "3" in elem_type:
                level = 3
            elif "four" in block_type or "four" in elem_type or "4" in elem_type:
                level = 4
            elif "five" in block_type or "five" in elem_type or "5" in elem_type:
                level = 5
            elif "six" in block_type or "six" in elem_type or "6" in elem_type:
                level = 6
            text = self._elements_to_markdown(value)
            return f"{'#' * level} {text}"

        if "code" in block_type or "code" in elem_type:
            text = self._extract_text_from_block(block_data)
            lang = first_elem.get("props", {}).get("language", "") if isinstance(first_elem, dict) else ""
            return f"```{lang}\n{text}\n```"

        if "blockquote" in block_type or "blockquote" in elem_type:
            text = self._elements_to_markdown(value)
            lines = text.split("\n")
            return "\n".join(f"> {line}" for line in lines)

        if "bulleted" in block_type or "bulleted" in elem_type:
            items = []
            for elem in value:
                item_text = self._element_to_markdown(elem)
                if item_text:
                    items.append(f"- {item_text}")
            return "\n".join(items)

        if "numbered" in block_type or "numbered" in elem_type:
            items = []
            for i, elem in enumerate(value, 1):
                item_text = self._element_to_markdown(elem)
                if item_text:
                    items.append(f"{i}. {item_text}")
            return "\n".join(items)

        if "todo" in block_type or "todo" in elem_type:
            items = []
            for elem in value:
                checked = elem.get("props", {}).get("checked", False) if isinstance(elem, dict) else False
                checkbox = "[x]" if checked else "[ ]"
                item_text = self._element_to_markdown(elem)
                if item_text:
                    items.append(f"- {checkbox} {item_text}")
            return "\n".join(items)

        if "divider" in block_type or "divider" in elem_type:
            return "---"

        if "image" in block_type or "image" in elem_type:
            props = first_elem.get("props", {}) if isinstance(first_elem, dict) else {}
            src = props.get("src", "")
            alt = props.get("alt", "Image")
            if src:
                return f"![{alt}]({src})"
            return ""

        if "link" in block_type or "link" in elem_type:
            return self._elements_to_markdown(value)

        # Default: treat as paragraph
        return self._elements_to_markdown(value)

    def _elements_to_markdown(self, elements: list) -> str:
        """Convert a list of Yoopta elements to Markdown text."""
        parts = []
        for elem in elements:
            md = self._element_to_markdown(elem)
            if md:
                parts.append(md)
        return "".join(parts)

    def _element_to_markdown(self, element: dict) -> str:
        """Convert a single Yoopta element to Markdown with inline formatting."""
        if not isinstance(element, dict):
            return ""

        # Direct text node with optional marks
        if "text" in element:
            text = element["text"]
            # Apply inline formatting
            if element.get("bold"):
                text = f"**{text}**"
            if element.get("italic"):
                text = f"*{text}*"
            if element.get("strike"):
                text = f"~~{text}~~"
            if element.get("code"):
                text = f"`{text}`"
            if element.get("underline"):
                # Markdown doesn't have native underline, use HTML
                text = f"<u>{text}</u>"
            return text

        # Link element
        elem_type = element.get("type", "").lower()
        if "link" in elem_type:
            props = element.get("props", {})
            url = props.get("url", props.get("href", ""))
            children = element.get("children", [])
            link_text = "".join(self._element_to_markdown(c) for c in children)
            if url:
                return f"[{link_text}]({url})"
            return link_text

        # Element with children
        children = element.get("children", [])
        if isinstance(children, list):
            return "".join(self._element_to_markdown(c) for c in children)

        return ""

    def get_html_content(self) -> str:
        """
        Export Yoopta JSON content to HTML format.

        Converts blocks to their HTML equivalents with proper semantic tags.

        Returns:
            str: HTML representation of the document.
        """
        import json
        from html import escape

        if not self.content:
            return ""

        try:
            if isinstance(self.content, str):
                content = json.loads(self.content)
            else:
                content = self.content

            if not isinstance(content, dict):
                return ""

            # Sort blocks by meta.order
            blocks = []
            for block_id, block_data in content.items():
                if not isinstance(block_data, dict):
                    continue
                order = block_data.get("meta", {}).get("order", 0)
                blocks.append((order, block_data))

            blocks.sort(key=lambda x: x[0])

            # Convert each block to HTML
            html_parts = []
            for _, block_data in blocks:
                block_html = self._block_to_html(block_data)
                if block_html:
                    html_parts.append(block_html)

            return "\n".join(html_parts)

        except (json.JSONDecodeError, TypeError, KeyError):
            from html import escape
            return f"<p>{escape(self.content)}</p>" if isinstance(self.content, str) else ""

    def _block_to_html(self, block_data: dict) -> str:
        """Convert a single Yoopta block to HTML."""
        from html import escape

        if not isinstance(block_data, dict):
            return ""

        block_type = block_data.get("type", "").lower()
        value = block_data.get("value", [])

        if not isinstance(value, list) or not value:
            return ""

        first_elem = value[0] if value else {}
        elem_type = first_elem.get("type", "").lower() if isinstance(first_elem, dict) else ""

        # Handle different block types
        if "heading" in block_type or "heading" in elem_type:
            level = 1
            if "one" in block_type or "one" in elem_type or "1" in elem_type:
                level = 1
            elif "two" in block_type or "two" in elem_type or "2" in elem_type:
                level = 2
            elif "three" in block_type or "three" in elem_type or "3" in elem_type:
                level = 3
            elif "four" in block_type or "four" in elem_type or "4" in elem_type:
                level = 4
            elif "five" in block_type or "five" in elem_type or "5" in elem_type:
                level = 5
            elif "six" in block_type or "six" in elem_type or "6" in elem_type:
                level = 6
            content = self._elements_to_html(value)
            return f"<h{level}>{content}</h{level}>"

        if "code" in block_type or "code" in elem_type:
            text = escape(self._extract_text_from_block(block_data))
            lang = first_elem.get("props", {}).get("language", "") if isinstance(first_elem, dict) else ""
            lang_attr = f' class="language-{escape(lang)}"' if lang else ""
            return f"<pre><code{lang_attr}>{text}</code></pre>"

        if "blockquote" in block_type or "blockquote" in elem_type:
            content = self._elements_to_html(value)
            return f"<blockquote>{content}</blockquote>"

        if "bulleted" in block_type or "bulleted" in elem_type:
            items = []
            for elem in value:
                item_html = self._element_to_html(elem)
                if item_html:
                    items.append(f"<li>{item_html}</li>")
            return "<ul>\n" + "\n".join(items) + "\n</ul>"

        if "numbered" in block_type or "numbered" in elem_type:
            items = []
            for elem in value:
                item_html = self._element_to_html(elem)
                if item_html:
                    items.append(f"<li>{item_html}</li>")
            return "<ol>\n" + "\n".join(items) + "\n</ol>"

        if "todo" in block_type or "todo" in elem_type:
            items = []
            for elem in value:
                checked = elem.get("props", {}).get("checked", False) if isinstance(elem, dict) else False
                checked_attr = " checked" if checked else ""
                item_html = self._element_to_html(elem)
                items.append(f'<li><input type="checkbox" disabled{checked_attr}> {item_html}</li>')
            return '<ul class="todo-list">\n' + "\n".join(items) + "\n</ul>"

        if "divider" in block_type or "divider" in elem_type:
            return "<hr>"

        if "image" in block_type or "image" in elem_type:
            props = first_elem.get("props", {}) if isinstance(first_elem, dict) else {}
            src = escape(props.get("src", ""))
            alt = escape(props.get("alt", "Image"))
            if src:
                return f'<img src="{src}" alt="{alt}">'
            return ""

        # Default: treat as paragraph
        content = self._elements_to_html(value)
        return f"<p>{content}</p>" if content else ""

    def _elements_to_html(self, elements: list) -> str:
        """Convert a list of Yoopta elements to HTML text."""
        parts = []
        for elem in elements:
            html = self._element_to_html(elem)
            if html:
                parts.append(html)
        return "".join(parts)

    def _element_to_html(self, element: dict) -> str:
        """Convert a single Yoopta element to HTML with inline formatting."""
        from html import escape

        if not isinstance(element, dict):
            return ""

        # Direct text node with optional marks
        if "text" in element:
            text = escape(element["text"])
            # Apply inline formatting (innermost first)
            if element.get("code"):
                text = f"<code>{text}</code>"
            if element.get("strike"):
                text = f"<del>{text}</del>"
            if element.get("underline"):
                text = f"<u>{text}</u>"
            if element.get("italic"):
                text = f"<em>{text}</em>"
            if element.get("bold"):
                text = f"<strong>{text}</strong>"
            if element.get("highlight"):
                text = f"<mark>{text}</mark>"
            return text

        # Link element
        elem_type = element.get("type", "").lower()
        if "link" in elem_type:
            props = element.get("props", {})
            url = escape(props.get("url", props.get("href", "")))
            children = element.get("children", [])
            link_text = "".join(self._element_to_html(c) for c in children)
            if url:
                return f'<a href="{url}">{link_text}</a>'
            return link_text

        # Element with children
        children = element.get("children", [])
        if isinstance(children, list):
            return "".join(self._element_to_html(c) for c in children)

        return ""


class DocumentPreviewQuerySet(OrganizationScopedQuerySet):
    """Scoped queryset with helpers for preview status."""

    def ready(self):
        return self.filter(status=DocumentPreview.Status.READY)


class DocumentPreview(models.Model):
    """Cached preview artifacts per document and preview kind."""

    class PreviewKind(models.TextChoices):
        THUMBNAIL = "thumbnail", "Thumbnail"
        SNIPPET = "snippet", "Snippet"
        LARGE = "large", "Large"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="previews",
        help_text="Document this preview belongs to",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        help_text="Organization for multi-tenant scoping",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Project scope for this preview",
    )
    preview_kind = models.CharField(
        max_length=20,
        choices=PreviewKind.choices,
        default=PreviewKind.THUMBNAIL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    content_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Hash of underlying content used for cache invalidation",
    )
    target_hash = models.CharField(
        max_length=128,
        blank=True,
        help_text="Hash this preview was generated against",
    )
    preview_file = models.ImageField(
        upload_to="previews/%Y/%m/%d/",
        null=True,
        blank=True,
        help_text="Generated preview image (WebP/PNG)",
    )
    preview_html = models.TextField(
        blank=True,
        help_text="Sanitized HTML snippet for text-based previews",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible metadata (dominant color, snippet, source info)",
    )
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DocumentPreviewQuerySet.as_manager()

    class Meta:
        verbose_name = "Document Preview"
        verbose_name_plural = "Document Previews"
        unique_together = [["document", "preview_kind"]]
        indexes = [
            models.Index(
                fields=["organization", "project", "status"],
                name="docpreview_scope_status",
            ),
        ]

    def __str__(self):
        return f"Preview({self.document_id}, {self.preview_kind}, {self.status})"

    def mark_failed(self, message: str):
        self.status = self.Status.FAILED
        self.error_message = message
        self.save(update_fields=["status", "error_message", "updated_at"])
