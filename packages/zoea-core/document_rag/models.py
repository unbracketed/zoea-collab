"""
Database models for Document RAG sessions.

These models track ephemeral RAG sessions where users can chat with
a collection of documents. Sessions are temporary and cleaned up after
a timeout period.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from accounts.managers import OrganizationScopedQuerySet

User = get_user_model()

# Default session TTL (2 hours)
DEFAULT_SESSION_TTL = timedelta(hours=2)


class RAGSession(models.Model):
    """
    An ephemeral RAG session scoped to selected documents.

    Sessions are short-lived and cleaned up when closed or after timeout.
    Each session references the project-scoped file search store and
    uses metadata filters to scope retrieval.
    """

    class ContextType(models.TextChoices):
        SINGLE = "single", "Single Document"
        FOLDER = "folder", "Folder Contents"
        CLIPBOARD = "clipboard", "Clipboard Items"
        COLLECTION = "collection", "Collection"

    class Status(models.TextChoices):
        INITIALIZING = "initializing", "Initializing"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        ERROR = "error", "Error"

    # Multi-tenant scoping
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="rag_sessions",
        help_text="Organization this session belongs to",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="rag_sessions",
        help_text="Project this session belongs to",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        related_name="rag_sessions",
        help_text="Workspace this session belongs to",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rag_sessions",
        help_text="User who started this session",
    )

    # Session identification
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Unique session identifier",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIALIZING,
        help_text="Current session status",
    )

    # Ephemeral Gemini store for this session
    gemini_store_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Ephemeral Gemini File Search store ID for this session",
    )

    # Document context
    context_type = models.CharField(
        max_length=20,
        choices=ContextType.choices,
        help_text="Type of document context (single, folder, clipboard, collection)",
    )
    context_id = models.PositiveIntegerField(
        help_text="ID of the context item (document, folder, clipboard, or collection)",
    )
    document_ids = models.JSONField(
        default=list,
        help_text="Array of document IDs included in this session",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        help_text="Session expiration time",
    )

    # Optional metadata
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional session title",
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if session failed to initialize",
    )

    # Use organization-scoped queryset for multi-tenant filtering
    objects = OrganizationScopedQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"RAGSession {self.session_id} ({self.status})"

    def save(self, *args, **kwargs):
        """Set expiration time on first save."""
        if not self.expires_at:
            self.expires_at = timezone.now() + DEFAULT_SESSION_TTL
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        """Check if session is still active and not expired."""
        return self.status == self.Status.ACTIVE and timezone.now() < self.expires_at

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return timezone.now() >= self.expires_at

    @property
    def document_count(self) -> int:
        """Get number of documents in this session."""
        return len(self.document_ids)

    def get_context_display(self) -> str:
        """Get human-readable context description."""
        type_name = self.get_context_type_display()
        return f"{type_name} with {self.document_count} documents"


class RAGSessionMessage(models.Model):
    """
    A message within a RAG session.

    Messages track the conversation between user and assistant,
    including which documents were retrieved for each response.
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(
        RAGSession,
        on_delete=models.CASCADE,
        related_name="messages",
        help_text="RAG session this message belongs to",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        help_text="Who sent this message",
    )
    content = models.TextField(
        help_text="The message content",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Track retrieved documents for assistant responses
    retrieved_documents = models.JSONField(
        default=list,
        help_text="Document sources retrieved for this response",
    )

    # Agent metadata for assistant messages
    thinking_steps = models.JSONField(
        default=list,
        blank=True,
        help_text="Agent reasoning steps (for assistant messages)",
    )
    model_used = models.CharField(
        max_length=100,
        blank=True,
        help_text="AI model used to generate this message",
    )
    telemetry = models.JSONField(
        default=dict,
        blank=True,
        help_text="Lightweight run telemetry (tokens, timing, tool usage)",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        preview = self.content[:50] + ("..." if len(self.content) > 50 else "")
        return f"{self.get_role_display()}: {preview}"

    @property
    def is_user_message(self) -> bool:
        """Check if this message is from a user."""
        return self.role == self.Role.USER

    @property
    def is_assistant_message(self) -> bool:
        """Check if this message is from an assistant."""
        return self.role == self.Role.ASSISTANT
