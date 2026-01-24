"""
RAG Session Manager.

Manages the lifecycle of RAG sessions including:
- Resolving document context for a session
- Tracking session state and TTL
- Leveraging the project-scoped file search store with metadata filters

Uses the configured file search backend via FileSearchRegistry in the indexing layer.
"""

import logging
import uuid
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

from documents.models import Collection, Document, Folder

from .models import DEFAULT_SESSION_TTL, RAGSession

logger = logging.getLogger(__name__)
User = get_user_model()


class RAGSessionManager:
    """
    Manages RAG session lifecycle:
    - Use the project-scoped file search store with metadata filters
    - Track session state
    - Cleanup on session close or timeout

    Uses the configured file search backend via the indexing layer.
    """

    def __init__(self, backend: str | None = None):
        """
        Initialize the session manager.

        Args:
            backend: Optional backend name. If not provided, uses the default
                     from FILE_SEARCH_BACKEND setting or registry default.
        """
        self.backend = backend

    async def create_session(
        self,
        user: User,
        context_type: str,
        context_id: int,
        project,
        *,
        ttl: timedelta | None = None,
    ) -> RAGSession:
        """
        Create a new RAG session and initialize document index.

        Args:
            user: User creating the session
            context_type: Type of context (single, folder, collection)
            context_id: ID of the context item
            project: Project instance
            ttl: Optional custom session TTL

        Returns:
            RAGSession instance

        Raises:
            ValueError: If context type is invalid or no documents found
        """
        # Get organization from project (async-safe)
        organization = await sync_to_async(lambda: project.organization)()

        # Resolve documents based on context type
        documents = await self._resolve_documents(
            context_type,
            context_id,
            organization=organization,
            project=project,
            user=user,
        )

        if not documents:
            raise ValueError(f"No documents found for {context_type} with ID {context_id}")

        # Create session record (initializing state)
        session = await RAGSession.objects.acreate(
            organization=organization,
            project=project,
            created_by=user,
            context_type=context_type,
            context_id=context_id,
            document_ids=[doc.id for doc in documents],
            status=RAGSession.Status.INITIALIZING,
            expires_at=timezone.now() + (ttl or DEFAULT_SESSION_TTL),
        )

        try:
            from file_search.indexing import ensure_project_store

            store_info = await sync_to_async(ensure_project_store)(project)
            session.gemini_store_id = store_info.store_id

            # Mark session as active (persistent store + metadata filters)
            session.status = RAGSession.Status.ACTIVE
            await session.asave(update_fields=["status", "gemini_store_id"])

            return session

        except Exception as e:
            # Mark session as error
            session.status = RAGSession.Status.ERROR
            session.error_message = str(e)
            await session.asave(update_fields=["status", "error_message"])
            raise

    async def close_session(self, session: RAGSession) -> None:
        """
        Close session and cleanup Gemini store.

        Args:
            session: RAGSession to close
        """
        session.status = RAGSession.Status.CLOSED
        await session.asave(update_fields=["status", "updated_at"])

    async def cleanup_expired_sessions(self) -> int:
        """
        Cleanup all expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        expired_sessions = RAGSession.objects.filter(
            status__in=[RAGSession.Status.ACTIVE, RAGSession.Status.INITIALIZING],
            expires_at__lt=timezone.now(),
        )

        count = 0
        async for session in expired_sessions:
            try:
                await self.close_session(session)
                count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup session {session.session_id}: {e}")

        return count

    async def _resolve_documents(
        self,
        context_type: str,
        context_id: int,
        *,
        organization,
        project,
        user: User,
    ) -> list[Document]:
        """
        Resolve document list based on context type.

        Args:
            context_type: Type of context
            context_id: ID of the context item
            organization: Organization for context
            project: Project for context
            user: User requesting the documents

        Returns:
            List of Document instances
        """
        if context_type == RAGSession.ContextType.SINGLE:
            try:
                doc = await Document.objects.select_subclasses().aget(
                    id=context_id,
                    organization=organization,
                    project=project,
                )
            except Document.DoesNotExist:
                return []
            return [doc]

        elif context_type == RAGSession.ContextType.FOLDER:
            try:
                folder = await Folder.objects.aget(
                    id=context_id,
                    organization=organization,
                    project=project,
                )
            except Folder.DoesNotExist:
                return []
            return await sync_to_async(list)(
                Document.objects.select_subclasses().filter(
                    folder=folder,
                    organization=organization,
                    project=project,
                )
            )

        elif context_type == RAGSession.ContextType.COLLECTION:
            try:
                collection = await Collection.objects.aget(
                    id=context_id,
                    organization=organization,
                    project=project,
                )
            except Collection.DoesNotExist:
                return []
            return await sync_to_async(list)(
                Document.objects.select_subclasses().filter(
                    collections=collection,
                    organization=organization,
                    project=project,
                )
            )

        else:
            raise ValueError(f"Invalid context type: {context_type}")

    async def find_active_session(
        self,
        context_type: str,
        context_id: int,
        project,
    ) -> RAGSession | None:
        """
        Find an existing active session for the given context.

        Args:
            context_type: Type of context
            context_id: ID of the context item
            project: Project instance

        Returns:
            RAGSession if found and active, None otherwise
        """
        try:
            session = await RAGSession.objects.filter(
                project=project,
                context_type=context_type,
                context_id=context_id,
                status=RAGSession.Status.ACTIVE,
            ).afirst()

            if session:
                # Check if expired
                if session.is_expired:
                    await self.close_session(session)
                    return None
                return session

            return None
        except Exception:
            return None

    async def get_session(self, session_id: str) -> RAGSession | None:
        """
        Get a session by ID.

        Args:
            session_id: Session UUID as string

        Returns:
            RAGSession if found and active, None otherwise
        """
        try:
            session_uuid = uuid.UUID(session_id)
            session = await RAGSession.objects.aget(session_id=session_uuid)

            # Check if expired
            if session.is_expired and session.status == RAGSession.Status.ACTIVE:
                await self.close_session(session)
                return None

            return session
        except (RAGSession.DoesNotExist, ValueError):
            return None
