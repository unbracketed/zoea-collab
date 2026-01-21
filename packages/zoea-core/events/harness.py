"""
Skill Execution Harness for isolated workflow execution.

Provides a secure, scoped execution environment for skills that:
- Restricts access to only the triggering organization/project
- Prevents modification of external entities
- Controls external API calls via domain allowlist
- Tracks all operations for audit logging
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypedDict
from urllib.parse import urlparse

from django.db import models, transaction
from django.utils import timezone

if TYPE_CHECKING:
    from accounts.models import Account
    from documents.models import Document, DocumentCollection
    from projects.models import Project
    from users.models import User

logger = logging.getLogger(__name__)


# =============================================================================
# Execution Context
# =============================================================================


class OperationType(str, Enum):
    """Types of operations that can be logged."""

    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"  # Not allowed, but logged if attempted
    EXTERNAL_CALL = "external_call"


@dataclass(frozen=True)
class SkillExecutionContext:
    """
    Immutable execution context for skill runs.

    This context is passed to all scoped APIs and tools to enforce
    boundaries on what the skill can access.

    Attributes:
        organization_id: ID of the owning organization
        project_id: Optional project scope (None for org-wide triggers)
        trigger_run_id: ID of the EventTriggerRun for tracking
        source_type: Type of source that triggered this run
        source_id: ID of the source object
        user_id: Optional user ID for attribution
        started_at: When execution started
        allowed_document_types: List of allowed document types to create
        max_documents_per_run: Maximum documents that can be created
        allowed_external_domains: Domains allowed for external calls
        rate_limit_per_domain: Max calls per domain per run
    """

    organization_id: int
    trigger_run_id: int
    source_type: str
    source_id: int
    project_id: int | None = None
    user_id: int | None = None
    started_at: datetime = field(default_factory=timezone.now)

    # Guardrails - configurable per trigger
    allowed_document_types: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"MarkdownDocument", "YooptaDocument", "TextDocument"}
        )
    )
    max_documents_per_run: int = 50
    allowed_external_domains: frozenset[str] = field(default_factory=frozenset)
    rate_limit_per_domain: int = 10

    def __post_init__(self):
        """Validate context after initialization."""
        if self.organization_id <= 0:
            raise ValueError("organization_id must be positive")
        if self.trigger_run_id <= 0:
            raise ValueError("trigger_run_id must be positive")

    @classmethod
    def from_trigger_run(
        cls,
        trigger_run,
        *,
        allowed_document_types: frozenset[str] | None = None,
        max_documents_per_run: int = 50,
        allowed_external_domains: frozenset[str] | None = None,
        rate_limit_per_domain: int = 10,
    ) -> SkillExecutionContext:
        """
        Create context from an EventTriggerRun.

        Args:
            trigger_run: EventTriggerRun instance
            allowed_document_types: Override allowed document types
            max_documents_per_run: Override max documents
            allowed_external_domains: Override allowed domains
            rate_limit_per_domain: Override rate limit

        Returns:
            SkillExecutionContext instance
        """
        from events.models import EventTriggerRun

        if not isinstance(trigger_run, EventTriggerRun):
            raise TypeError(f"Expected EventTriggerRun, got {type(trigger_run)}")

        # Get allowed domains from trigger config if not overridden
        if allowed_external_domains is None:
            config = trigger_run.trigger.agent_config or {}
            domains = config.get("allowed_external_domains", [])
            allowed_external_domains = frozenset(domains)

        return cls(
            organization_id=trigger_run.organization_id,
            project_id=trigger_run.trigger.project_id,
            trigger_run_id=trigger_run.id,
            source_type=trigger_run.source_type,
            source_id=trigger_run.source_id,
            allowed_document_types=allowed_document_types
            or frozenset({"MarkdownDocument", "YooptaDocument", "TextDocument"}),
            max_documents_per_run=max_documents_per_run,
            allowed_external_domains=allowed_external_domains,
            rate_limit_per_domain=rate_limit_per_domain,
        )


# =============================================================================
# Operation Audit Log
# =============================================================================


class OperationLogEntry(TypedDict):
    """Entry in the operation audit log."""

    timestamp: str
    operation: str
    model: str
    object_id: int | None
    details: dict[str, Any]
    allowed: bool
    reason: str | None


@dataclass
class OperationAuditLog:
    """
    Audit log for operations performed during skill execution.

    Tracks all read/write operations for debugging and compliance.
    """

    context: SkillExecutionContext
    entries: list[OperationLogEntry] = field(default_factory=list)
    documents_created: int = 0
    external_calls: dict[str, int] = field(default_factory=dict)

    def log(
        self,
        operation: OperationType,
        model: str,
        object_id: int | None = None,
        details: dict[str, Any] | None = None,
        allowed: bool = True,
        reason: str | None = None,
    ) -> None:
        """Log an operation."""
        self.entries.append(
            OperationLogEntry(
                timestamp=timezone.now().isoformat(),
                operation=operation.value,
                model=model,
                object_id=object_id,
                details=details or {},
                allowed=allowed,
                reason=reason,
            )
        )

        if not allowed:
            logger.warning(
                "Blocked operation: %s on %s (id=%s) - %s",
                operation.value,
                model,
                object_id,
                reason,
            )

    def increment_documents_created(self) -> bool:
        """
        Increment document count and check limit.

        Returns:
            True if within limit, False if limit exceeded
        """
        self.documents_created += 1
        return self.documents_created <= self.context.max_documents_per_run

    def record_external_call(self, domain: str) -> bool:
        """
        Record an external call and check rate limit.

        Returns:
            True if within limit, False if limit exceeded
        """
        self.external_calls[domain] = self.external_calls.get(domain, 0) + 1
        return self.external_calls[domain] <= self.context.rate_limit_per_domain

    def to_dict(self) -> dict[str, Any]:
        """Export log as dictionary for storage."""
        return {
            "trigger_run_id": self.context.trigger_run_id,
            "started_at": self.context.started_at.isoformat(),
            "documents_created": self.documents_created,
            "external_calls": self.external_calls,
            "entry_count": len(self.entries),
            "blocked_operations": sum(1 for e in self.entries if not e["allowed"]),
            "entries": self.entries[-100:],  # Keep last 100 entries
        }


# =============================================================================
# Scoped Project API
# =============================================================================


class ScopedProjectAPIError(Exception):
    """Raised when a scoped API operation is not allowed."""

    pass


class ScopedProjectAPI:
    """
    Guardrailed API for accessing project data within skill execution.

    Provides scoped access to:
    - Documents (read/write within project)
    - Document collections
    - Email messages (read-only, source only)
    - Project metadata (read-only)

    Prevents:
    - Access to other organizations
    - Access to other projects (unless org-wide trigger)
    - Deletion of any entities
    - Modification of source entities
    """

    def __init__(self, context: SkillExecutionContext):
        """
        Initialize scoped API.

        Args:
            context: Execution context with scope boundaries
        """
        self.context = context
        self.audit_log = OperationAuditLog(context)
        self._loaded_project: Project | None = None
        self._loaded_organization: Account | None = None

    # -------------------------------------------------------------------------
    # Organization/Project Access
    # -------------------------------------------------------------------------

    @property
    def organization(self) -> Account:
        """Get the scoped organization (lazy loaded)."""
        if self._loaded_organization is None:
            from accounts.models import Account

            self._loaded_organization = Account.objects.get(
                id=self.context.organization_id
            )
            self.audit_log.log(
                OperationType.READ,
                "Account",
                self.context.organization_id,
                {"field": "organization"},
            )
        return self._loaded_organization

    @property
    def project(self) -> Project | None:
        """Get the scoped project if set (lazy loaded)."""
        if self.context.project_id is None:
            return None
        if self._loaded_project is None:
            from projects.models import Project

            self._loaded_project = Project.objects.get(id=self.context.project_id)
            self.audit_log.log(
                OperationType.READ,
                "Project",
                self.context.project_id,
                {"field": "project"},
            )
        return self._loaded_project

    # -------------------------------------------------------------------------
    # Document Access
    # -------------------------------------------------------------------------

    def get_document(self, document_id: int) -> Document:
        """
        Get a document by ID, enforcing scope.

        Args:
            document_id: ID of the document

        Returns:
            Document instance (with proper subclass via select_subclasses)

        Raises:
            ScopedProjectAPIError: If document is not in scope
        """
        from documents.models import Document

        try:
            # Use select_subclasses to get the proper document type
            doc = Document.objects.select_subclasses().get(id=document_id)
        except Document.DoesNotExist:
            self.audit_log.log(
                OperationType.READ,
                "Document",
                document_id,
                {},
                allowed=False,
                reason="Document not found",
            )
            raise ScopedProjectAPIError(f"Document {document_id} not found")

        # Verify organization scope
        if doc.organization_id != self.context.organization_id:
            self.audit_log.log(
                OperationType.READ,
                "Document",
                document_id,
                {"doc_org": doc.organization_id},
                allowed=False,
                reason="Document belongs to different organization",
            )
            raise ScopedProjectAPIError("Access denied: document not in scope")

        # Verify project scope if set
        if self.context.project_id is not None:
            if doc.project_id != self.context.project_id:
                self.audit_log.log(
                    OperationType.READ,
                    "Document",
                    document_id,
                    {"doc_project": doc.project_id},
                    allowed=False,
                    reason="Document belongs to different project",
                )
                raise ScopedProjectAPIError("Access denied: document not in project")

        self.audit_log.log(OperationType.READ, "Document", document_id)
        return doc

    def list_documents(
        self,
        *,
        document_type: str | None = None,
        limit: int = 100,
    ) -> list[Document]:
        """
        List documents in scope.

        Args:
            document_type: Optional filter by document type (class name like "Markdown")
            limit: Maximum number of documents to return

        Returns:
            List of Document instances (with proper subclasses)
        """
        from documents.models import Document

        # Use select_subclasses to get proper document types
        qs = Document.objects.select_subclasses().filter(
            organization_id=self.context.organization_id
        )

        if self.context.project_id is not None:
            qs = qs.filter(project_id=self.context.project_id)

        # Filter by document type if specified (filter after fetching since it's inheritance-based)
        docs = list(qs[:limit])

        if document_type:
            # Map common document type names to their class names
            type_map = {
                "MarkdownDocument": "Markdown",
                "TextDocument": "TextDocument",
                "YooptaDocument": "YooptaDocument",
            }
            target_type = type_map.get(document_type, document_type)
            docs = [d for d in docs if d.get_type_name() == target_type]

        self.audit_log.log(
            OperationType.READ,
            "Document",
            None,
            {"count": len(docs), "document_type": document_type},
        )
        return docs

    def search_documents(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search documents using the project's file search store.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of search results with document info
        """
        if self.context.project_id is None:
            self.audit_log.log(
                OperationType.READ,
                "DocumentSearch",
                None,
                {"query": query},
                allowed=False,
                reason="Document search requires project scope",
            )
            raise ScopedProjectAPIError("Document search requires project scope")

        try:
            from file_search import FileSearchRegistry
            from projects.models import Project

            project = Project.objects.get(id=self.context.project_id)
            store_id = project.gemini_store_id

            if not store_id:
                self.audit_log.log(
                    OperationType.READ,
                    "DocumentSearch",
                    None,
                    {"query": query},
                    allowed=False,
                    reason="Project has no file search store configured",
                )
                return []

            store = FileSearchRegistry.get()
            results = store.search(store_id, query, top_k=limit)

            # Convert SearchResult objects to dicts
            result_dicts = [
                {
                    "document_id": r.document_id,
                    "title": r.title,
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ]

            self.audit_log.log(
                OperationType.READ,
                "DocumentSearch",
                None,
                {"query": query, "results": len(result_dicts)},
            )
            return result_dicts
        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # Document Creation
    # -------------------------------------------------------------------------

    def create_document(
        self,
        document_type: str,
        name: str,
        content: str | dict[str, Any],
        *,
        collection: DocumentCollection | None = None,
        description: str = "",
    ) -> Document:
        """
        Create a new document within scope.

        Args:
            document_type: Type of document (must be in allowed_document_types)
            name: Document name
            content: Document content (string or dict for JSON types)
            collection: Optional collection to add document to
            description: Optional document description

        Returns:
            Created Document instance

        Raises:
            ScopedProjectAPIError: If document type not allowed or limit exceeded
        """
        # Check document type allowlist
        if document_type not in self.context.allowed_document_types:
            self.audit_log.log(
                OperationType.CREATE,
                "Document",
                None,
                {"document_type": document_type},
                allowed=False,
                reason=f"Document type '{document_type}' not in allowlist",
            )
            raise ScopedProjectAPIError(
                f"Document type '{document_type}' not allowed. "
                f"Allowed: {self.context.allowed_document_types}"
            )

        # Check document count limit
        if not self.audit_log.increment_documents_created():
            self.audit_log.log(
                OperationType.CREATE,
                "Document",
                None,
                {"document_type": document_type},
                allowed=False,
                reason=f"Document limit ({self.context.max_documents_per_run}) exceeded",
            )
            raise ScopedProjectAPIError(
                f"Document limit ({self.context.max_documents_per_run}) exceeded"
            )

        # Import document models - use specific subclasses
        from documents.models import Markdown, TextDocument, YooptaDocument

        with transaction.atomic():
            # Select the appropriate model based on document_type
            if document_type == "MarkdownDocument":
                doc_class = Markdown
            elif document_type == "TextDocument":
                doc_class = TextDocument
            elif document_type == "YooptaDocument":
                doc_class = YooptaDocument
            else:
                raise ScopedProjectAPIError(
                    f"Unknown document type: {document_type}"
                )

            # Create the document
            doc = doc_class(
                organization_id=self.context.organization_id,
                project_id=self.context.project_id,
                name=name,
                description=description,
            )
            doc._skip_event_dispatch = True

            # Set content
            if isinstance(content, dict):
                doc.content = content
            else:
                doc.content = str(content)

            doc.save()

            # Add to collection if provided
            if collection:
                from django.contrib.contenttypes.models import ContentType

                from documents.models import (
                    CollectionItemDirection,
                    CollectionItemSourceChannel,
                    DocumentCollectionItem,
                )

                doc_content_type = ContentType.objects.get_for_model(doc)
                position = collection.reserve_position(CollectionItemDirection.RIGHT)
                DocumentCollectionItem.objects.create(
                    collection=collection,
                    position=position,
                    direction_added=CollectionItemDirection.RIGHT,
                    content_type=doc_content_type,
                    object_id=str(doc.pk),
                    source_channel=CollectionItemSourceChannel.WORKFLOW,
                    source_metadata={
                        "document_type": document_type,
                        "created_by_harness": True,
                    },
                )
                collection.save(update_fields=["sequence_head", "sequence_tail", "updated_at"])

            self.audit_log.log(
                OperationType.CREATE,
                "Document",
                doc.id,
                {"document_type": document_type, "name": name},
            )

            return doc

    def create_collection(
        self,
        name: str,
        description: str = "",
    ) -> DocumentCollection:
        """
        Create a document collection for artifacts.

        Args:
            name: Collection name
            description: Optional description

        Returns:
            Created DocumentCollection instance
        """
        from documents.models import DocumentCollection

        collection = DocumentCollection.objects.create(
            organization_id=self.context.organization_id,
            project_id=self.context.project_id,
            name=name,
            description=description,
        )

        self.audit_log.log(
            OperationType.CREATE,
            "DocumentCollection",
            collection.id,
            {"name": name},
        )

        return collection

    # -------------------------------------------------------------------------
    # Source Entity Access (Read-Only)
    # -------------------------------------------------------------------------

    def get_source_entity(self) -> models.Model:
        """
        Get the source entity that triggered this run.

        Returns:
            The source model instance (e.g., EmailMessage, Document)

        Raises:
            ScopedProjectAPIError: If source type unknown
        """
        source_type = self.context.source_type
        source_id = self.context.source_id

        if source_type == "email_message":
            from email_gateway.models import EmailMessage

            entity = EmailMessage.objects.get(id=source_id)
        elif source_type == "document":
            from documents.models import Document

            entity = Document.objects.get(id=source_id)
        else:
            raise ScopedProjectAPIError(f"Unknown source type: {source_type}")

        self.audit_log.log(
            OperationType.READ,
            source_type,
            source_id,
            {"is_source": True},
        )
        return entity

    # -------------------------------------------------------------------------
    # Deletion Prevention
    # -------------------------------------------------------------------------

    def delete_document(self, document_id: int) -> None:
        """
        Attempt to delete a document (always blocked).

        Raises:
            ScopedProjectAPIError: Always raised - deletion not allowed
        """
        self.audit_log.log(
            OperationType.DELETE,
            "Document",
            document_id,
            {},
            allowed=False,
            reason="Deletion not allowed in skill execution",
        )
        raise ScopedProjectAPIError("Deletion not allowed in skill execution")


# =============================================================================
# External Call Handler
# =============================================================================


class ExternalCallHandler:
    """
    Handler for external HTTP calls with domain allowlist.

    Controls which external domains skills can call and tracks usage.
    """

    # Default domains always allowed (safe, public APIs)
    DEFAULT_ALLOWED_DOMAINS: frozenset[str] = frozenset(
        {
            # Search engines (via DuckDuckGo)
            "duckduckgo.com",
            "html.duckduckgo.com",
            # Wikipedia
            "wikipedia.org",
            "en.wikipedia.org",
            # Public APIs that don't require auth
            "api.github.com",
            "httpbin.org",
        }
    )

    def __init__(self, context: SkillExecutionContext, audit_log: OperationAuditLog):
        """
        Initialize handler.

        Args:
            context: Execution context with allowed domains
            audit_log: Audit log for tracking calls
        """
        self.context = context
        self.audit_log = audit_log
        self.allowed_domains = (
            self.DEFAULT_ALLOWED_DOMAINS | context.allowed_external_domains
        )

    def is_allowed(self, url: str) -> tuple[bool, str | None]:
        """
        Check if a URL is allowed.

        Args:
            url: URL to check

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]

            # Check exact match
            if domain in self.allowed_domains:
                return True, None

            # Check wildcard subdomain match (e.g., "*.example.com")
            for allowed in self.allowed_domains:
                if allowed.startswith("*."):
                    base = allowed[2:]
                    if domain == base or domain.endswith(f".{base}"):
                        return True, None

            return False, f"Domain '{domain}' not in allowlist"

        except Exception as e:
            return False, f"Invalid URL: {e}"

    def check_and_record(self, url: str) -> None:
        """
        Check if URL is allowed and record the call.

        Args:
            url: URL being called

        Raises:
            ScopedProjectAPIError: If domain not allowed or rate limited
        """
        allowed, reason = self.is_allowed(url)

        if not allowed:
            self.audit_log.log(
                OperationType.EXTERNAL_CALL,
                "HTTP",
                None,
                {"url": url},
                allowed=False,
                reason=reason,
            )
            raise ScopedProjectAPIError(f"External call blocked: {reason}")

        # Extract domain for rate limiting
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if not self.audit_log.record_external_call(domain):
            self.audit_log.log(
                OperationType.EXTERNAL_CALL,
                "HTTP",
                None,
                {"url": url, "domain": domain},
                allowed=False,
                reason=f"Rate limit ({self.context.rate_limit_per_domain}) exceeded for {domain}",
            )
            raise ScopedProjectAPIError(
                f"Rate limit exceeded for domain: {domain}"
            )

        self.audit_log.log(
            OperationType.EXTERNAL_CALL,
            "HTTP",
            None,
            {"url": url, "domain": domain},
        )


# =============================================================================
# Main Harness
# =============================================================================


class SkillExecutionHarness:
    """
    Main harness for isolated skill execution.

    Combines all scoped APIs and handlers into a single interface.

    Example:
        harness = SkillExecutionHarness.from_trigger_run(run)

        # Access scoped APIs
        doc = harness.api.get_document(123)
        new_doc = harness.api.create_document("MarkdownDocument", "Result", content)

        # External calls are checked
        harness.external.check_and_record("https://api.example.com/data")

        # Get audit log when done
        log_data = harness.get_audit_log()
    """

    def __init__(self, context: SkillExecutionContext):
        """
        Initialize harness.

        Args:
            context: Execution context
        """
        self.context = context
        self.api = ScopedProjectAPI(context)
        self.external = ExternalCallHandler(context, self.api.audit_log)

    @classmethod
    def from_trigger_run(
        cls,
        trigger_run,
        **context_kwargs,
    ) -> SkillExecutionHarness:
        """
        Create harness from an EventTriggerRun.

        Args:
            trigger_run: EventTriggerRun instance
            **context_kwargs: Additional context configuration

        Returns:
            SkillExecutionHarness instance
        """
        context = SkillExecutionContext.from_trigger_run(
            trigger_run, **context_kwargs
        )
        return cls(context)

    def get_audit_log(self) -> dict[str, Any]:
        """Get the audit log as a dictionary."""
        return self.api.audit_log.to_dict()

    @property
    def organization(self):
        """Get the scoped organization."""
        return self.api.organization

    @property
    def project(self):
        """Get the scoped project (may be None)."""
        return self.api.project
