"""
Django management command to test the email gateway webhook with attachments.

This command simulates a Mailgun webhook POST to test email processing
without going through the actual SMTP/email delivery process.

Usage:
    # Basic test email
    python manage.py test_email_webhook --sender user@example.com --recipient inbox@project.zoea.studio

    # With attachments
    python manage.py test_email_webhook --sender user@example.com --recipient inbox@project.zoea.studio \
        --attachment /path/to/file.pdf --attachment /path/to/image.png

    # With custom subject and body
    python manage.py test_email_webhook --sender user@example.com --recipient inbox@project.zoea.studio \
        --subject "Test Email" --body "This is the email body"
"""

import hashlib
import hmac
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from email_gateway.api import receive_inbound_email


class Command(BaseCommand):
    help = "Test the email gateway webhook with optional attachments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sender",
            type=str,
            required=True,
            help="Sender email address (must be a registered user in the organization)",
        )
        parser.add_argument(
            "--recipient",
            type=str,
            required=True,
            help="Recipient email address (e.g., inbox@project.zoea.studio)",
        )
        parser.add_argument(
            "--subject",
            type=str,
            default="Test Email from Management Command",
            help="Email subject line",
        )
        parser.add_argument(
            "--body",
            type=str,
            default="This is a test email sent via the test_email_webhook management command.",
            help="Email body text",
        )
        parser.add_argument(
            "--attachment",
            type=str,
            action="append",
            dest="attachments",
            help="Path to attachment file (can be specified multiple times)",
        )
        parser.add_argument(
            "--message-id",
            type=str,
            default=None,
            help="Custom Message-ID (auto-generated if not specified)",
        )
        parser.add_argument(
            "--in-reply-to",
            type=str,
            default="",
            help="In-Reply-To header for threading",
        )
        parser.add_argument(
            "--skip-signature",
            action="store_true",
            help="Skip Mailgun signature (for development without API key)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending",
        )

    def handle(self, *args, **options):
        sender = options["sender"]
        recipient = options["recipient"]
        subject = options["subject"]
        body = options["body"]
        attachments = options.get("attachments") or []
        message_id = options.get("message_id") or f"<{uuid.uuid4()}@test.zoea.studio>"
        in_reply_to = options.get("in_reply_to") or ""
        skip_signature = options.get("skip_signature", False)
        dry_run = options.get("dry_run", False)

        # Generate Mailgun signature components
        timestamp = str(int(time.time()))
        token = uuid.uuid4().hex

        if skip_signature:
            signature = "test-signature"
        else:
            api_key = getattr(settings, "MAILGUN_API_KEY", None)
            if not api_key:
                self.stdout.write(
                    self.style.WARNING(
                        "MAILGUN_API_KEY not set. Using skip-signature mode."
                    )
                )
                signature = "test-signature"
            else:
                message = f"{timestamp}{token}"
                signature = hmac.new(
                    key=api_key.encode("utf-8"),
                    msg=message.encode("utf-8"),
                    digestmod=hashlib.sha256,
                ).hexdigest()

        # Prepare POST data
        post_data = {
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body-plain": body,
            "body-html": f"<p>{body}</p>",
            "stripped-text": body,
            "stripped-html": f"<p>{body}</p>",
            "Message-Id": message_id,
            "In-Reply-To": in_reply_to,
            "References": in_reply_to,
            "from": f"Test User <{sender}>",
            "timestamp": timestamp,
            "token": token,
            "signature": signature,
            "attachment-count": str(len(attachments)),
            "content-id-map": "{}",
        }

        # Prepare attachments
        files = {}
        content_id_map = {}
        for i, attachment_path in enumerate(attachments):
            path = Path(attachment_path)
            if not path.exists():
                raise CommandError(f"Attachment file not found: {attachment_path}")

            with open(path, "rb") as f:
                content = f.read()

            # Determine content type
            content_type = self._guess_content_type(path)
            field_name = f"attachment-{i + 1}"

            files[field_name] = SimpleUploadedFile(
                name=path.name,
                content=content,
                content_type=content_type,
            )
            content_id_map[field_name] = path.name

            self.stdout.write(
                f"  Attachment: {path.name} ({content_type}, {len(content)} bytes)"
            )

        if content_id_map:
            import json
            post_data["content-id-map"] = json.dumps(content_id_map)

        # Display what will be sent
        self.stdout.write(self.style.NOTICE("\n=== Email Webhook Test ==="))
        self.stdout.write(f"From: {sender}")
        self.stdout.write(f"To: {recipient}")
        self.stdout.write(f"Subject: {subject}")
        self.stdout.write(f"Message-ID: {message_id}")
        self.stdout.write(f"Attachments: {len(attachments)}")
        if in_reply_to:
            self.stdout.write(f"In-Reply-To: {in_reply_to}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] Not sending webhook"))
            return

        # Create a mock request
        factory = RequestFactory()
        request = factory.post(
            "/api/email/inbound/",
            data=post_data,
        )
        request.FILES.update(files)

        # Call the webhook handler
        self.stdout.write("\nSending webhook...")

        try:
            response = receive_inbound_email(
                request,
                sender=post_data["sender"],
                recipient=post_data["recipient"],
                subject=post_data["subject"],
                body_plain=post_data["body-plain"],
                body_html=post_data["body-html"],
                stripped_text=post_data["stripped-text"],
                stripped_html=post_data["stripped-html"],
                message_id=post_data["Message-Id"],
                in_reply_to=post_data["In-Reply-To"],
                references=post_data["References"],
                timestamp=post_data["timestamp"],
                token=post_data["token"],
                signature=post_data["signature"],
                from_header=post_data["from"],
                content_id_map=post_data["content-id-map"],
                attachment_count=len(attachments),
            )

            self.stdout.write(self.style.SUCCESS(f"\nWebhook response: {response}"))

            # Show created records
            from email_gateway.models import EmailMessage, EmailThread

            try:
                email_msg = EmailMessage.objects.get(message_id=message_id)
                self.stdout.write(f"\nEmailMessage ID: {email_msg.id}")
                self.stdout.write(f"Status: {email_msg.status}")

                if email_msg.email_thread:
                    thread = email_msg.email_thread
                    self.stdout.write(f"\nEmailThread ID: {thread.id}")
                    self.stdout.write(f"Conversation ID: {thread.conversation_id}")

                    if thread.attachments_id:
                        self.stdout.write(f"Attachments Collection ID: {thread.attachments_id}")
                        items = thread.attachments.items.all()
                        self.stdout.write(f"Attachment Items: {items.count()}")
                        for item in items:
                            meta = item.source_metadata or {}
                            self.stdout.write(
                                f"  - {meta.get('filename', 'Unknown')} "
                                f"(doc_id={item.object_id})"
                            )

                stored = email_msg.stored_attachments.all()
                if stored:
                    self.stdout.write(f"\nStored Attachments: {stored.count()}")
                    for att in stored:
                        self.stdout.write(
                            f"  - {att.filename} ({att.content_type}, "
                            f"doc_id={att.document_id})"
                        )

            except EmailMessage.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING("EmailMessage not found (may have been rejected)")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nError: {e}"))
            raise

    def _guess_content_type(self, path: Path) -> str:
        """Guess MIME type from file extension."""
        ext = path.suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".txt": "text/plain",
            ".html": "text/html",
            ".csv": "text/csv",
            ".json": "application/json",
            ".xml": "application/xml",
            ".zip": "application/zip",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return content_types.get(ext, "application/octet-stream")
