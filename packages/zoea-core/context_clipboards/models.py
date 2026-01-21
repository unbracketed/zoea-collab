"""Database models for the clipboard system.

.. deprecated:: 2.0
    This module is deprecated. Use :mod:`documents.models.DocumentCollection`
    with collection_type='notebook' instead. The Clipboard, ClipboardItem, and
    VirtualClipboardNode models will be removed in a future release.

    Migration guide:
    - Clipboard -> DocumentCollection (collection_type='notebook')
    - ClipboardItem -> DocumentCollectionItem
    - VirtualClipboardNode -> Consider DocumentCollectionItem with transient flag

    See documents/services/notebooks.py for the new API.
"""

import warnings
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet


class ClipboardDirection(models.TextChoices):
    """Deque direction used when inserting an item."""

    LEFT = "left", "Left"
    RIGHT = "right", "Right"


class ClipboardSourceChannel(models.TextChoices):
    """High-level origin hint for clipboard items."""

    CONVERSATION = "conversation", "Conversation"
    MESSAGE = "message", "Message"
    DOCUMENT = "document", "Document"
    WORKFLOW = "workflow", "Workflow"
    CANVAS = "canvas", "Canvas"
    CODE = "code", "Code Snippet"
    UNKNOWN = "unknown", "Unknown"


class ClipboardQuerySet(OrganizationScopedQuerySet):
    """Custom queryset with convenience filters for clipboards."""

    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)

    def for_owner(self, owner):
        return self.filter(owner=owner)

    def active(self):
        return self.filter(is_active=True)

    def recent(self):
        return self.filter(is_recent=True)


class Clipboard(models.Model):
    """Base clipboard storing ordered references to contextual artifacts.

    .. deprecated:: 2.0
        Use DocumentCollection with collection_type='notebook' instead.
        This model will be removed in a future release.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="clipboards",
        help_text="Workspace that scopes this clipboard",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clipboards",
        help_text="User that owns/created the clipboard",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    is_recent = models.BooleanField(default=False)
    sequence_head = models.BigIntegerField(
        default=0,
        help_text="Tracks the head index for deque-style operations",
    )
    sequence_tail = models.BigIntegerField(
        default=-1,
        help_text="Tracks the tail index for deque-style operations",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ClipboardQuerySet.as_manager()

    class Meta:
        ordering = ["-activated_at", "-updated_at"]
        indexes = [
            models.Index(fields=["workspace", "owner"]),
        ]
        constraints = [
            models.UniqueConstraint(
                condition=Q(is_active=True),
                fields=["workspace", "owner"],
                name="unique_active_clipboard_per_user",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable helper
        return self.name

    def activate(self):
        """Mark this clipboard as active and update bookkeeping fields."""

        self.is_active = True
        self.is_recent = False
        self.activated_at = timezone.now()

    def deactivate(self):
        """Mark this clipboard as inactive and push it into the recent list."""

        self.is_active = False
        self.is_recent = True

    def reserve_position(self, direction: str) -> int:
        """Reserve the next available deque position for the given direction."""

        if direction == ClipboardDirection.LEFT:
            self.sequence_head -= 1
            return self.sequence_head
        self.sequence_tail += 1
        return self.sequence_tail


class ClipboardItem(models.Model):
    """Represents a single entry in a clipboard.

    .. deprecated:: 2.0
        Use DocumentCollectionItem instead.
        This model will be removed in a future release.
    """

    clipboard = models.ForeignKey(
        Clipboard,
        on_delete=models.CASCADE,
        related_name="items",
    )
    position = models.BigIntegerField(
        help_text="Relative ordering value supporting deque semantics",
    )
    direction_added = models.CharField(
        max_length=5,
        choices=ClipboardDirection.choices,
        default=ClipboardDirection.RIGHT,
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clipboard_items_added",
    )
    is_pinned = models.BooleanField(default=False)
    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    object_id = models.CharField(max_length=255, blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")
    virtual_node = models.ForeignKey(
        "VirtualClipboardNode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clipboard_items",
    )
    source_channel = models.CharField(
        max_length=32,
        choices=ClipboardSourceChannel.choices,
        default=ClipboardSourceChannel.UNKNOWN,
    )
    source_metadata = models.JSONField(default=dict, blank=True)
    preview = models.JSONField(
        null=True,
        blank=True,
        help_text="Custom preview data for the clipboard item (e.g., chat bubble, diagram thumbnail)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "-created_at"]
        indexes = [
            models.Index(fields=["clipboard", "position"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - helper for admin
        return f"ClipboardItem({self.clipboard_id}, pos={self.position})"


class VirtualClipboardNode(models.Model):
    """Stores transient workspace artifacts that may later be persisted.

    .. deprecated:: 2.0
        Consider using DocumentCollectionItem with appropriate flags instead.
        This model will be removed in a future release.
    """

    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="virtual_clipboard_nodes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="virtual_clipboard_nodes",
    )
    node_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    preview_text = models.TextField(blank=True)
    preview_image = models.URLField(blank=True)
    origin_reference = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    materialized_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="materialized_virtual_nodes",
    )
    materialized_object_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["workspace", "node_type"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"VirtualNode({self.node_type})"

    def is_expired(self) -> bool:
        """Return True if the node has passed its TTL."""

        return bool(self.expires_at and timezone.now() > self.expires_at)
