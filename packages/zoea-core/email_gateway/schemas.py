"""
Pydantic schemas for Mailgun webhook payloads.

Mailgun sends inbound email data as form-urlencoded or multipart POST data.
Field names use hyphens (e.g., 'body-plain', 'stripped-text') which require aliases.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class MailgunWebhookPayload(BaseModel):
    """
    Schema for Mailgun inbound email webhook POST data.

    Mailgun sends emails as form-urlencoded data with hyphenated field names.
    This schema maps those to Python-friendly attribute names using aliases.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Sender/recipient info
    sender: str = Field(description="Sender email address")
    from_header: str = Field(alias="from", description="From header with display name")
    recipient: str = Field(description="Recipient email address")
    subject: str = Field(default="", description="Email subject")

    # Body content
    body_plain: str = Field(default="", alias="body-plain", description="Plain text body")
    body_html: str = Field(default="", alias="body-html", description="HTML body")
    stripped_text: str = Field(
        default="", alias="stripped-text", description="Plain text with quoted parts removed"
    )
    stripped_html: str = Field(
        default="", alias="stripped-html", description="HTML with quoted parts removed"
    )
    stripped_signature: str = Field(
        default="", alias="stripped-signature", description="Extracted signature"
    )

    # RFC 2822 threading headers
    message_id: str = Field(alias="Message-Id", description="RFC 2822 Message-ID")
    in_reply_to: str = Field(default="", alias="In-Reply-To", description="In-Reply-To header")
    references: str = Field(
        default="", alias="References", description="References header (space-separated IDs)"
    )
    date: str = Field(default="", alias="Date", description="Email date header")

    # Attachments
    attachment_count: int = Field(
        default=0, alias="attachment-count", description="Number of attachments"
    )
    content_id_map: str = Field(
        default="", alias="content-id-map", description="JSON map of Content-IDs to attachment names"
    )

    # Mailgun signature verification (required for security)
    timestamp: str = Field(description="Unix timestamp from Mailgun")
    token: str = Field(description="Random token from Mailgun")
    signature: str = Field(description="HMAC-SHA256 signature")

    # Optional custom variables
    mailgun_variables: str = Field(
        default="", alias="X-Mailgun-Variables", description="Custom JSON variables"
    )


class WebhookResponse(BaseModel):
    """Response schema for webhook endpoint."""

    status: str = Field(description="Status of webhook processing")
    message_id: Optional[str] = Field(
        default=None, description="Internal message ID if stored"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")


class EmailMessageResponse(BaseModel):
    """Schema for API responses about email messages."""

    id: int
    message_id: str
    sender: str
    recipient: str
    subject: str
    status: str
    received_at: str
    processed_at: Optional[str] = None


class EmailThreadResponse(BaseModel):
    """Schema for API responses about email threads."""

    id: int
    thread_id: str
    subject: str
    initiator_email: str
    recipient_address: str
    status: str
    email_count: int
    first_email_at: str
    last_email_at: str
    conversation_id: int


class AttachmentCollectionItemOut(BaseModel):
    """Schema for attachment collection items."""

    id: int
    position: int
    source_channel: str
    source_metadata: dict
    document_id: Optional[int] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    url: Optional[str] = None
    created_at: str


class AttachmentCollectionOut(BaseModel):
    """Schema for email thread attachment collection."""

    collection_id: Optional[int] = None
    thread_id: int
    item_count: int
    items: list[AttachmentCollectionItemOut]
