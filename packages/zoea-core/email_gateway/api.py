"""
Django Ninja API router for email webhook endpoints.
"""

import hashlib
import hmac
import logging
import json
from typing import Dict

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from ninja import Router, Form
from ninja.errors import HttpError

from accounts.utils import get_user_organization

from .models import EmailMessage, EmailAttachment, EmailThread
from .schemas import WebhookResponse, AttachmentCollectionOut, AttachmentCollectionItemOut

router = Router(tags=["email"])
logger = logging.getLogger(__name__)


def _parse_content_id_map(content_id_map: str) -> Dict:
    """Parse Mailgun content-id-map JSON safely."""
    if not content_id_map:
        return {}
    try:
        parsed = json.loads(content_id_map)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        logger.warning("Failed to parse content-id-map value")
        return {}


def _match_content_id(content_id_map: Dict, field_name: str, filename: str) -> str:
    """
    Try to resolve a Content-ID for an attachment using the Mailgun content-id-map.

    Mailgun sends a mapping of content IDs to attachment field names. We attempt
    to match by field name (e.g., attachment-1) or filename for robustness.
    """
    if not content_id_map:
        return ""

    # Direct lookup by field name
    value = content_id_map.get(field_name)
    if value:
        if isinstance(value, list) and value:
            return str(value[0])
        return str(value)

    # Fallback: find the content-id whose value references the filename/field
    for cid, names in content_id_map.items():
        if isinstance(names, list) and (field_name in names or filename in names):
            return str(cid)
        if names == field_name or names == filename:
            return str(cid)

    return ""


def _save_attachments(email_msg: EmailMessage, uploaded_files, content_id_map: str) -> list[dict]:
    """
    Persist uploaded attachments to storage and return metadata for EmailMessage.attachments.
    """
    files = uploaded_files or {}
    if not files:
        return []

    parsed_content_ids = _parse_content_id_map(content_id_map)
    metadata: list[dict] = []

    for field_name, uploaded_file in files.items():
        if not isinstance(uploaded_file, UploadedFile):
            continue

        content_id = _match_content_id(parsed_content_ids, field_name, uploaded_file.name)
        attachment = EmailAttachment.objects.create(
            organization=email_msg.organization,
            email_message=email_msg,
            filename=uploaded_file.name,
            content_type=getattr(uploaded_file, "content_type", "") or "",
            size=getattr(uploaded_file, "size", 0) or 0,
            content_id=content_id,
        )

        attachment.file.save(uploaded_file.name, uploaded_file, save=True)

        metadata.append(
            {
                "id": attachment.id,
                "filename": uploaded_file.name,
                "content_type": getattr(uploaded_file, "content_type", "") or "",
                "size": getattr(uploaded_file, "size", 0) or 0,
                "content_id": content_id or "",
                "field_name": field_name,
                "file": attachment.file.name,
            }
        )

    return metadata


def verify_mailgun_signature(timestamp: str, token: str, signature: str) -> bool:
    """
    Verify Mailgun webhook signature using HMAC-SHA256.

    Mailgun signs webhooks by concatenating timestamp + token and signing
    with the API key using HMAC-SHA256.

    Args:
        timestamp: Unix timestamp from Mailgun
        token: Random token from Mailgun
        signature: HMAC-SHA256 signature from Mailgun

    Returns:
        True if signature is valid, False otherwise
    """
    api_key = settings.MAILGUN_API_KEY
    if not api_key:
        logger.warning("MAILGUN_API_KEY not configured, skipping signature verification")
        return True  # Allow in development without key

    # Compute expected signature
    message = f"{timestamp}{token}"
    expected_signature = hmac.new(
        key=api_key.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@router.post("/inbound/", response=WebhookResponse)
def receive_inbound_email(
    request,
    # Sender/recipient info
    sender: str = Form(...),
    recipient: str = Form(...),
    subject: str = Form(default=""),
    # Use alias mapping for hyphenated fields
    body_plain: str = Form(default="", alias="body-plain"),
    body_html: str = Form(default="", alias="body-html"),
    stripped_text: str = Form(default="", alias="stripped-text"),
    stripped_html: str = Form(default="", alias="stripped-html"),
    # RFC 2822 headers
    message_id: str = Form(..., alias="Message-Id"),
    in_reply_to: str = Form(default="", alias="In-Reply-To"),
    references: str = Form(default="", alias="References"),
    # Mailgun signature verification
    timestamp: str = Form(...),
    token: str = Form(...),
    signature: str = Form(...),
    # From header with display name
    from_header: str = Form(default="", alias="from"),
    # Attachment info
    content_id_map: str = Form(default="", alias="content-id-map"),
    # Attachment info
    attachment_count: int = Form(default=0, alias="attachment-count"),
):
    """
    Receive inbound email webhook from Mailgun.

    This endpoint:
    1. Verifies the Mailgun signature for security
    2. Checks for duplicate messages (idempotent)
    3. Stores the email with status='queued' for background processing
    4. Returns 200 OK to acknowledge receipt

    Note: This endpoint does NOT require authentication as it's called by Mailgun.
    Security is provided by signature verification.
    """
    # 1. Verify Mailgun signature
    if not verify_mailgun_signature(timestamp, token, signature):
        logger.warning(f"Invalid Mailgun signature for message {message_id}")
        raise HttpError(401, "Invalid signature")

    # 2. Check for duplicate (idempotent)
    if EmailMessage.objects.filter(message_id=message_id).exists():
        logger.info(f"Duplicate email received: {message_id}")
        return WebhookResponse(
            status="duplicate",
            message_id=message_id,
        )

    # 3. Store the email message
    # Note: organization is determined during background processing based on sender
    # For now, we store without organization - it will be set during processing
    try:
        email_msg = EmailMessage.objects.create(
            # Organization will be set during processing
            organization_id=None,  # Temporarily null - set during processing
            message_id=message_id,
            in_reply_to=in_reply_to,
            references=references,
            sender=sender,
            recipient=recipient,
            subject=subject,
            stripped_text=stripped_text,
            body_plain=body_plain,
            body_html=body_html,
            mailgun_timestamp=timestamp,
            mailgun_token=token,
            mailgun_signature=signature,
            attachments=[],
            headers={
                "From": from_header,
                "Message-Id": message_id,
                "In-Reply-To": in_reply_to,
                "References": references,
            },
            raw_post_data={
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "from": from_header,
                "body-plain": body_plain,
                "body-html": body_html,
                "stripped-text": stripped_text,
                "stripped-html": stripped_html,
                "Message-Id": message_id,
                "In-Reply-To": in_reply_to,
                "References": references,
                "timestamp": timestamp,
            "token": token,
            "signature": signature,
            "attachment-count": attachment_count,
            "content-id-map": content_id_map,
        },
            status='queued',
        )

        logger.info(f"Stored email {message_id} from {sender} as EmailMessage {email_msg.id}")

        # 4. Persist attachments before returning success
        try:
            attachments_metadata = _save_attachments(
                email_msg=email_msg,
                uploaded_files=request.FILES,
                content_id_map=content_id_map,
            )
            if attachments_metadata:
                email_msg.attachments = attachments_metadata
                email_msg.save(update_fields=['attachments'])
        except Exception as e:
            logger.exception(f"Failed to save attachments for {message_id}: {e}")
            raise HttpError(500, f"Failed to save attachments: {e}") from e

        # 5. Process email (runs immediately in development)
        # In production, this would be enqueued to a background worker
        from .tasks import process_email_message
        try:
            process_email_message(email_msg.id)
        except Exception as e:
            # Log but don't fail the webhook - email is stored and can be retried
            logger.error(f"Background processing failed for {message_id}: {e}")

        return WebhookResponse(
            status="queued",
            message_id=message_id,
        )

    except Exception as e:
        logger.exception(f"Failed to store email {message_id}: {e}")
        raise HttpError(500, f"Failed to store email: {e}")


@router.get("/health/")
def email_health_check(request):
    """Health check endpoint for email gateway."""
    return {"status": "ok", "service": "email_gateway"}


@router.get("/threads/{thread_id}/attachments/", response=AttachmentCollectionOut)
def list_thread_attachments(request, thread_id: int):
    """
    Return attachments collection for an email thread.

    Returns the attachments as collection items with document references,
    similar to how conversation artifacts are handled.
    """
    organization = get_user_organization(request.user)
    if not organization:
        raise HttpError(403, "User has no organization")

    try:
        thread = EmailThread.objects.select_related(
            "organization", "project", "attachments"
        ).get(id=thread_id, organization=organization)
    except EmailThread.DoesNotExist as exc:
        raise HttpError(404, "Email thread not found") from exc

    # If no attachments collection, return empty
    if not thread.attachments_id:
        return AttachmentCollectionOut(
            collection_id=None,
            thread_id=thread_id,
            item_count=0,
            items=[],
        )

    # Get collection items with their source metadata
    items = thread.attachments.items.select_related("content_type").order_by("position")

    serialized_items = []
    for item in items:
        meta = item.source_metadata or {}

        # Build URL for the file if we have a document reference
        url = None
        doc_id = None
        if item.content_type and item.object_id:
            try:
                doc = item.content_object
                if doc and hasattr(doc, "file") and doc.file:
                    url = request.build_absolute_uri(doc.file.url)
                doc_id = int(item.object_id) if item.object_id else None
            except Exception:
                pass

        serialized_items.append(AttachmentCollectionItemOut(
            id=item.id,
            position=item.position,
            source_channel=item.source_channel,
            source_metadata=meta,
            document_id=doc_id,
            filename=meta.get("filename"),
            content_type=meta.get("content_type"),
            file_size=meta.get("file_size"),
            url=url,
            created_at=item.created_at.isoformat(),
        ))

    return AttachmentCollectionOut(
        collection_id=thread.attachments_id,
        thread_id=thread_id,
        item_count=len(serialized_items),
        items=serialized_items,
    )
