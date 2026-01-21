"""
Email processing service for handling inbound emails.

This service handles the asynchronous processing of inbound emails,
including sender validation, thread resolution, and conversation creation.
"""

import logging
from datetime import datetime
from typing import Optional, Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from organizations.models import OrganizationUser

from accounts.utils import get_user_organization, get_user_default_project, get_project_default_workspace
from chat.models import Conversation, Message
from documents.models import (
    Folder,
    FileDocument,
    DocumentCollectionItem,
    CollectionItemSourceChannel,
    CollectionItemDirection,
)
from projects.email_utils import resolve_email_recipient

from .models import EmailThread, EmailMessage, EmailAttachment

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailProcessingError(Exception):
    """Exception raised when email processing fails."""
    pass


class InvalidRecipientError(EmailProcessingError):
    """Exception raised when recipient email doesn't match any project/workspace."""
    pass


class UnauthorizedSenderError(EmailProcessingError):
    """Exception raised when sender is not a member of the recipient's organization."""
    pass


def validate_inbound_email(sender_email: str, recipient_email: str) -> Tuple[User, object, object, object]:
    """
    Validate inbound email sender and recipient.

    Validates that:
    1. The recipient email resolves to a known project/workspace
    2. The sender email belongs to a user in that organization

    Args:
        sender_email: Email address of the sender
        recipient_email: Email address of the recipient (should be a project/workspace email)

    Returns:
        Tuple of (User, Organization, Project, Workspace or None)

    Raises:
        InvalidRecipientError: If recipient doesn't match any project/workspace
        UnauthorizedSenderError: If sender is not a member of the organization
    """
    # 1. Resolve recipient to project/workspace
    resolved = resolve_email_recipient(recipient_email)

    if not resolved.project:
        logger.warning(f"Unknown recipient email: {recipient_email}")
        raise InvalidRecipientError(f"Unknown recipient: {recipient_email}")

    organization = resolved.organization
    project = resolved.project
    workspace = resolved.workspace

    logger.info(
        f"Resolved recipient {recipient_email} to "
        f"org={organization.slug}, project={project.slug}"
        + (f", workspace={workspace.slug}" if workspace else "")
        + f" via {resolved.resolved_via}"
    )

    # 2. Validate sender is a member of the organization
    try:
        user = User.objects.get(email__iexact=sender_email)
    except User.DoesNotExist:
        logger.warning(f"Unknown sender email: {sender_email}")
        raise UnauthorizedSenderError(f"Sender {sender_email} is not a registered user")

    # Check if user is a member of the organization
    is_member = OrganizationUser.objects.filter(
        organization=organization,
        user=user
    ).exists()

    if not is_member:
        logger.warning(
            f"Sender {sender_email} is not a member of organization {organization.name}"
        )
        raise UnauthorizedSenderError(
            f"Sender {sender_email} is not a member of organization {organization.name}"
        )

    logger.info(f"Validated sender {sender_email} as member of {organization.name}")

    return user, organization, project, workspace


class EmailProcessingService:
    """
    Service for processing inbound emails and creating conversations.

    This service handles:
    1. Sender validation - matching email addresses to users
    2. Thread resolution - RFC 2822 threading via References/In-Reply-To
    3. Conversation/Message creation - linking emails to chat system
    """

    def process_email(self, email_message_id: int) -> bool:
        """
        Process a queued email message.

        Args:
            email_message_id: ID of the EmailMessage to process

        Returns:
            True if processing succeeded, False otherwise

        Raises:
            EmailProcessingError: If processing fails
        """
        try:
            email_msg = EmailMessage.objects.get(id=email_message_id)
        except EmailMessage.DoesNotExist:
            raise EmailProcessingError(f"EmailMessage {email_message_id} not found")

        if email_msg.status not in ('received', 'queued'):
            logger.warning(f"EmailMessage {email_message_id} already processed (status={email_msg.status})")
            return False

        # Mark as processing
        email_msg.status = 'processing'
        email_msg.save(update_fields=['status'])

        try:
            with transaction.atomic():
                # 1. Validate sender and recipient, get resolved project/workspace
                user, organization, project, workspace = validate_inbound_email(
                    sender_email=email_msg.sender,
                    recipient_email=email_msg.recipient
                )

                # Update email message with organization and user
                email_msg.organization = organization
                email_msg.sender_user = user
                # Ensure stored attachments inherit organization for scoping
                email_msg.stored_attachments.update(organization=organization)

                # 2. Resolve thread (find or create)
                # Pass resolved project/workspace to avoid re-resolving
                email_thread = self._resolve_thread(
                    email_msg, organization, user,
                    resolved_project=project,
                    resolved_workspace=workspace
                )

                # 3. Create chat message
                chat_message = Message.objects.create(
                    conversation=email_thread.conversation,
                    role='user',
                    content=email_msg.stripped_text or email_msg.body_plain,
                )
                conversation_user = email_thread.conversation.created_by

                # 4. Update email message with resolved data
                email_msg.email_thread = email_thread
                email_msg.chat_message = chat_message
                email_msg.status = 'processed'
                email_msg.processed_at = timezone.now()
                email_msg.save()

                # 5. Ensure thread has an attachment folder and convert stored attachments
                self._convert_attachments_to_documents(
                    email_msg=email_msg,
                    email_thread=email_thread,
                    conversation_user=conversation_user,
                )

                # 5. Update thread stats
                email_thread.email_count = email_thread.emails.count()
                email_thread.last_email_at = email_msg.received_at
                email_thread.save(update_fields=['email_count', 'last_email_at', 'attachment_folder'])

                logger.info(
                    f"Processed email {email_msg.message_id} -> "
                    f"Thread {email_thread.id}, Message {chat_message.id}"
                )

                # 6. Dispatch event for any configured triggers
                self._dispatch_email_received_event(
                    email_msg=email_msg,
                    email_thread=email_thread,
                    organization=organization,
                    project=project,
                    user=user,
                )

                return True

        except Exception as e:
            # Mark as failed and log error
            email_msg.status = 'failed'
            email_msg.error_message = str(e)
            email_msg.save(update_fields=['status', 'error_message'])
            logger.exception(f"Failed to process email {email_message_id}: {e}")
            raise EmailProcessingError(str(e)) from e

    def _validate_sender(self, sender_email: str) -> Tuple[Optional[User], Optional[object]]:
        """
        Validate sender email and find associated user and organization.

        Args:
            sender_email: Email address of the sender

        Returns:
            Tuple of (User or None, Organization or None)
        """
        # Try to find user by email
        try:
            user = User.objects.get(email__iexact=sender_email)
            organization = get_user_organization(user)
            return user, organization
        except User.DoesNotExist:
            # No user with this email - try to find any organization that
            # might be configured to accept emails from this sender
            # For now, we don't have a way to do this without a user
            logger.warning(f"No user found for sender email: {sender_email}")
            return None, None

    def _resolve_thread(
        self,
        email_msg: EmailMessage,
        organization,
        user: Optional[User],
        resolved_project=None,
        resolved_workspace=None
    ) -> EmailThread:
        """
        Resolve email thread using RFC 2822 threading rules.

        Threading resolution order:
        1. Check References header (most reliable)
        2. Check In-Reply-To header
        3. Create new thread if no match

        Args:
            email_msg: The email message to resolve thread for
            organization: The organization for this thread
            user: The sender user (may be None)
            resolved_project: Pre-resolved project from recipient validation
            resolved_workspace: Pre-resolved workspace from recipient validation

        Returns:
            EmailThread instance (existing or newly created)
        """
        # Try to find existing thread

        # 1. Check References header (space-separated list of Message-IDs)
        if email_msg.references:
            reference_ids = email_msg.references.split()
            for ref_id in reference_ids:
                thread = self._find_thread_by_message_id(ref_id)
                if thread:
                    logger.debug(f"Found thread via References: {thread.id}")
                    return thread

        # 2. Check In-Reply-To header
        if email_msg.in_reply_to:
            thread = self._find_thread_by_message_id(email_msg.in_reply_to)
            if thread:
                logger.debug(f"Found thread via In-Reply-To: {thread.id}")
                return thread

        # 3. Create new thread
        return self._create_new_thread(
            email_msg, organization, user,
            resolved_project=resolved_project,
            resolved_workspace=resolved_workspace
        )

    def _find_thread_by_message_id(self, message_id: str) -> Optional[EmailThread]:
        """
        Find an existing thread by a message ID.

        Searches for an EmailMessage with the given message_id and returns
        its parent thread.

        Args:
            message_id: RFC 2822 Message-ID to search for

        Returns:
            EmailThread if found, None otherwise
        """
        try:
            existing_msg = EmailMessage.objects.select_related('email_thread').get(
                message_id=message_id
            )
            return existing_msg.email_thread
        except EmailMessage.DoesNotExist:
            return None

    def _create_new_thread(
        self,
        email_msg: EmailMessage,
        organization,
        user: Optional[User],
        resolved_project=None,
        resolved_workspace=None
    ) -> EmailThread:
        """
        Create a new email thread and associated conversation.

        Args:
            email_msg: The initiating email message
            organization: Organization for the thread
            user: Initiating user (may be None)
            resolved_project: Pre-resolved project from recipient validation
            resolved_workspace: Pre-resolved workspace from recipient validation

        Returns:
            Newly created EmailThread
        """
        # Use pre-resolved project/workspace if provided
        if resolved_project:
            project = resolved_project
            workspace = resolved_workspace or get_project_default_workspace(project)
        else:
            # Fall back to resolving from recipient email (for backwards compatibility)
            resolved = resolve_email_recipient(email_msg.recipient)
            if resolved.project:
                project = resolved.project
                workspace = resolved.workspace
                logger.info(
                    f"Resolved recipient {email_msg.recipient} to "
                    f"project={project.slug} via {resolved.resolved_via}"
                    + (f", workspace={workspace.slug}" if workspace else "")
                )
            elif user:
                # Fall back to user's default project/workspace
                project = get_user_default_project(user)
                workspace = get_project_default_workspace(project) if project else None
                logger.info(
                    f"Could not resolve recipient {email_msg.recipient}, "
                    f"using default project for user {user.email}"
                )
            else:
                project = None
                workspace = None
                logger.warning(
                    f"Could not resolve recipient {email_msg.recipient} "
                    "and no user to get defaults from"
                )

        # Create conversation first (required for EmailThread)
        # Use a system user for non-authenticated senders
        conversation_user = user
        if not conversation_user:
            # Try to get a system user or the first admin
            try:
                # Get any admin user from the organization
                org_user = OrganizationUser.objects.filter(
                    organization=organization,
                    is_admin=True
                ).select_related('user').first()
                if org_user:
                    conversation_user = org_user.user
            except Exception:
                pass

        if not conversation_user:
            raise EmailProcessingError(
                "Cannot create conversation: no valid user available"
            )

        conversation = Conversation.objects.create(
            organization=organization,
            project=project,
            workspace=workspace,
            created_by=conversation_user,
            agent_name='EmailGateway',
            title=f"Email: {email_msg.subject[:100]}" if email_msg.subject else "Email Thread",
        )

        # Create the email thread
        email_thread = EmailThread.objects.create(
            organization=organization,
            project=project,
            workspace=workspace,
            conversation=conversation,
            thread_id=email_msg.message_id,  # First message ID becomes thread ID
            subject=email_msg.subject,
            initiator_email=email_msg.sender,
            initiator_user=user,
            recipient_address=email_msg.recipient,
            status='active',
            email_count=1,
            first_email_at=email_msg.received_at,
            last_email_at=email_msg.received_at,
        )

        logger.info(
            f"Created new EmailThread {email_thread.id} with "
            f"Conversation {conversation.id} for {email_msg.sender}"
        )

        return email_thread

    def _ensure_attachment_folder(self, email_thread: EmailThread, conversation_user: User):
        """
        Create or return the hidden folder used for storing email attachments.
        """
        if email_thread.attachment_folder:
            return email_thread.attachment_folder

        # Must have workspace/project to create folder
        if not email_thread.workspace or not email_thread.project:
            logger.warning("Email thread missing workspace/project; skipping attachment folder creation")
            return None

        folder_name = f"Email Thread {email_thread.id}"

        folder, _ = Folder.objects.get_or_create(
            workspace=email_thread.workspace,
            parent=None,
            name=folder_name,
            defaults={
                "description": f"Attachments for email thread {email_thread.thread_id}",
                "project": email_thread.project,
                "organization": email_thread.organization,
                "is_system": True,
                "created_by": conversation_user,
            },
        )

        if not email_thread.attachment_folder_id:
            email_thread.attachment_folder = folder

        return folder

    def _convert_attachments_to_documents(
        self,
        email_msg: EmailMessage,
        email_thread: EmailThread,
        conversation_user: User,
    ):
        """
        Convert stored EmailAttachments into FileDocument records under the thread folder.
        Also adds them as items to the thread's attachments collection.
        """
        attachments = list(email_msg.stored_attachments.all())
        if not attachments:
            return

        folder = self._ensure_attachment_folder(email_thread, conversation_user)
        if not folder:
            logger.warning(f"Cannot convert attachments; missing folder for thread {email_thread.id}")
            return

        # Get or create the attachments collection for this thread
        collection = email_thread.get_or_create_attachments(created_by=conversation_user)

        metadata_by_filename = {meta.get("filename"): meta for meta in (email_msg.attachments or [])}
        created_docs = []

        for attachment in attachments:
            file_doc = FileDocument(
                organization=email_thread.organization,
                project=email_thread.project,
                workspace=email_thread.workspace,
                name=attachment.filename,
                description="Email attachment",
                original_filename=attachment.filename,
                content_type=attachment.content_type,
                folder=folder,
                created_by=conversation_user,
            )
            if attachment.file:
                file_doc.file.save(attachment.filename, attachment.file, save=False)
                file_doc.file_size = attachment.size or getattr(file_doc.file, "size", None)

            file_doc.save()
            created_docs.append(file_doc)

            attachment.document = file_doc
            attachment.organization = email_thread.organization
            attachment.save(update_fields=["document", "organization"])

            meta = metadata_by_filename.get(attachment.filename)
            if meta is not None:
                meta["document_id"] = file_doc.id
                meta["file"] = file_doc.file.name

        # Add documents to the attachments collection
        self._add_attachments_to_collection(
            collection=collection,
            documents=created_docs,
            email_msg=email_msg,
            added_by=conversation_user,
        )

        # Persist updated attachment metadata if changed
        email_msg.attachments = list(metadata_by_filename.values()) if metadata_by_filename else email_msg.attachments
        email_msg.save(update_fields=["attachments"])

    def _add_attachments_to_collection(
        self,
        collection,
        documents: list[FileDocument],
        email_msg: EmailMessage,
        added_by: User,
    ):
        """
        Add document attachments as items to the collection.

        Args:
            collection: DocumentCollection to add items to
            documents: List of FileDocument instances to add
            email_msg: Source email message for metadata
            added_by: User who added the attachments
        """
        from django.contrib.contenttypes.models import ContentType

        if not documents:
            return

        file_doc_ct = ContentType.objects.get_for_model(FileDocument)

        for doc in documents:
            position = collection.reserve_position(CollectionItemDirection.RIGHT)
            DocumentCollectionItem.objects.create(
                collection=collection,
                position=position,
                direction_added=CollectionItemDirection.RIGHT,
                added_by=added_by,
                content_type=file_doc_ct,
                object_id=str(doc.pk),
                source_channel=CollectionItemSourceChannel.EMAIL,
                source_metadata={
                    "email_message_id": email_msg.id,
                    "message_id": email_msg.message_id,
                    "filename": doc.original_filename,
                    "content_type": doc.content_type,
                    "file_size": doc.file_size,
                },
            )

        # Save the updated sequence tail
        collection.save(update_fields=["sequence_tail"])

    def _dispatch_email_received_event(
        self,
        email_msg: EmailMessage,
        email_thread: EmailThread,
        organization,
        project,
        user,
    ):
        """
        Dispatch EMAIL_RECEIVED event to any configured triggers.

        This allows skills to be automatically executed when emails are received,
        enabling workflows like data extraction, CRM sync, or webhook calls.

        Note: The dispatch is deferred via transaction.on_commit() to ensure
        the email message and related objects are fully committed before any
        async trigger tasks try to access them.

        Args:
            email_msg: The processed EmailMessage
            email_thread: The EmailThread containing the message
            organization: Organization scope
            project: Project scope (may be None)
            user: Sender user (may be None)
        """
        try:
            from events.dispatcher import dispatch_event
            from events.models import EventType

            # Build event data from email message
            # Note: We need to capture values now since the objects may be
            # in a different state after the transaction commits
            attachments = list(email_msg.stored_attachments.values_list(
                "filename", flat=True
            ))

            event_data = {
                "message_id": email_msg.message_id,
                "thread_id": email_thread.id,
                "subject": email_msg.subject,
                "sender": email_msg.sender,
                "recipient": email_msg.recipient,
                "body": email_msg.stripped_text or email_msg.body_plain,
                "body_html": email_msg.body_html,
                "attachments": attachments,
                "received_at": email_msg.received_at.isoformat() if email_msg.received_at else None,
                "conversation_id": email_thread.conversation_id,
            }

            # Capture IDs for the deferred dispatch
            email_msg_id = email_msg.id
            org_id = organization.id if organization else None
            project_id = project.id if project else None
            user_id = user.id if user else None

            def _do_dispatch():
                """Dispatch event after transaction commits."""
                try:
                    # Re-fetch objects to ensure we have committed state
                    from accounts.models import Account
                    from django.contrib.auth import get_user_model
                    from projects.models import Project

                    User = get_user_model()

                    org = Account.objects.get(id=org_id) if org_id else None
                    proj = Project.objects.get(id=project_id) if project_id else None
                    usr = User.objects.get(id=user_id) if user_id else None

                    dispatch_event(
                        event_type=EventType.EMAIL_RECEIVED,
                        source_type="email_message",
                        source_id=email_msg_id,
                        event_data=event_data,
                        organization=org,
                        project=proj,
                        user=usr,
                    )
                except Exception as e:
                    logger.warning(f"Failed to dispatch email event: {e}", exc_info=True)

            # Defer dispatch until after the current transaction commits
            transaction.on_commit(_do_dispatch)

        except ImportError:
            # Events app may not be installed
            logger.debug("Events app not available, skipping event dispatch")
        except Exception as e:
            # Don't fail email processing if event dispatch setup fails
            logger.warning(f"Failed to setup email event dispatch: {e}", exc_info=True)
