"""
Document service for creating documents in Zoea.

Provides methods to create Markdown and other document types,
with support for automatic folder hierarchy creation.
"""

import logging
from typing import TYPE_CHECKING, Optional

from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from accounts.models import Account
    from documents.models import Folder, Markdown
    from projects.models import Project

logger = logging.getLogger(__name__)


class DocumentService:
    """
    Service for creating documents in the Zoea database.

    Handles:
    - Creating Markdown documents
    - Auto-creating folder hierarchies
    - Setting proper organization/project scoping

    Example:
        doc_service = DocumentService(org, project, user)
        doc = await doc_service.create_markdown(
            name="Implementation Plan",
            content="# Plan\n\nDetails...",
            folder_path="SDLC/Specs/Issue-7"
        )
    """

    def __init__(
        self,
        organization: "Account",
        project: "Project",
        user: "User",
        workspace=None,  # Deprecated, ignored
    ):
        """
        Initialize document service with Django context.

        Args:
            organization: The organization for document scoping
            project: The project for document scoping
            user: The user creating documents
            workspace: Deprecated, ignored
        """
        self.organization = organization
        self.project = project
        self.user = user

    async def create_markdown(
        self,
        name: str,
        content: str,
        folder_path: Optional[str] = None,
        description: str = "",
    ) -> "Markdown":
        """
        Create a Markdown document asynchronously.

        Args:
            name: Document name (will add .md extension if missing)
            content: Markdown content
            folder_path: Optional folder path (e.g., "SDLC/Specs/Issue-7")
            description: Optional document description

        Returns:
            Created Markdown document instance
        """
        return await sync_to_async(self._create_markdown_sync)(
            name, content, folder_path, description
        )

    def _create_markdown_sync(
        self,
        name: str,
        content: str,
        folder_path: Optional[str] = None,
        description: str = "",
    ) -> "Markdown":
        """Synchronous implementation of create_markdown."""
        from documents.models import Markdown

        folder = None
        if folder_path:
            folder = self._get_or_create_folder(folder_path)

        # Ensure .md extension
        if not name.endswith(".md"):
            name = f"{name}.md"

        doc = Markdown.objects.create(
            organization=self.organization,
            project=self.project,
            name=name,
            content=content,
            description=description,
            folder=folder,
            created_by=self.user,
            file_size=len(content.encode("utf-8")),
        )

        logger.info(f"Created Markdown document: {doc.name} (id={doc.id})")
        if folder:
            logger.debug(f"Document folder: {folder_path}")

        return doc

    def _get_or_create_folder(self, path: str) -> "Folder":
        """
        Get or create a folder hierarchy from a path string.

        Args:
            path: Folder path like "SDLC/Specs/Issue-7"

        Returns:
            The leaf Folder instance
        """
        from documents.models import Folder

        parts = path.strip("/").split("/")
        parent = None

        for part in parts:
            folder, created = Folder.objects.get_or_create(
                project=self.project,
                parent=parent,
                name=part,
                defaults={
                    "organization": self.organization,
                    "created_by": self.user,
                },
            )
            if created:
                logger.debug(f"Created folder: {part}")
            parent = folder

        return parent

    def create_markdown_sync(
        self,
        name: str,
        content: str,
        folder_path: Optional[str] = None,
        description: str = "",
    ) -> "Markdown":
        """
        Synchronous version of create_markdown for use in non-async contexts.

        Args:
            name: Document name
            content: Markdown content
            folder_path: Optional folder path
            description: Optional document description

        Returns:
            Created Markdown document instance
        """
        return self._create_markdown_sync(name, content, folder_path, description)
