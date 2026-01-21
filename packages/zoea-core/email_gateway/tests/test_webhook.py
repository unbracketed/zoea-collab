"""
Tests for email webhook endpoint.
"""

import hashlib
import hmac
import json
import pytest
from urllib.parse import urlencode
from unittest.mock import patch
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile

from email_gateway.models import EmailMessage, EmailAttachment


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


def encode_form_data(payload: dict) -> str:
    """Encode a dict as application/x-www-form-urlencoded string."""
    return urlencode(payload)


@pytest.fixture
def mailgun_payload():
    """Create a sample Mailgun webhook payload."""
    return {
        'sender': 'sender@example.com',
        'recipient': 'inbox@mail.zoea.studio',
        'subject': 'Test Email',
        'from': 'Test Sender <sender@example.com>',
        'body-plain': 'This is the plain text body.',
        'body-html': '<html><body>This is the HTML body.</body></html>',
        'stripped-text': 'This is the stripped text.',
        'stripped-html': '<html><body>This is the stripped HTML.</body></html>',
        'Message-Id': '<test-msg-123@example.com>',
        'In-Reply-To': '',
        'References': '',
        'timestamp': '1701792000',
        'token': 'test-token-12345',
        'signature': '',  # Will be computed
        'attachment-count': '0',
    }


def compute_signature(api_key: str, timestamp: str, token: str) -> str:
    """Compute Mailgun signature."""
    message = f"{timestamp}{token}"
    return hmac.new(
        key=api_key.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()


@pytest.mark.django_db
class TestInboundWebhook:
    """Tests for the inbound email webhook endpoint."""

    def test_webhook_stores_email(self, client, mailgun_payload):
        """Test that webhook stores email message."""
        # Without MAILGUN_API_KEY, signature verification is skipped
        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = None

            response = client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        assert data['message_id'] == '<test-msg-123@example.com>'

        # Verify email was stored
        msg = EmailMessage.objects.get(message_id='<test-msg-123@example.com>')
        assert msg.sender == 'sender@example.com'
        assert msg.recipient == 'inbox@mail.zoea.studio'
        assert msg.subject == 'Test Email'
        assert msg.stripped_text == 'This is the stripped text.'

    def test_webhook_duplicate_handling(self, client, mailgun_payload):
        """Test that duplicate emails are handled correctly."""
        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = None

            # First request
            response1 = client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )
            assert response1.status_code == 200
            assert response1.json()['status'] == 'queued'

            # Second request with same Message-Id
            response2 = client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )
            assert response2.status_code == 200
            assert response2.json()['status'] == 'duplicate'

        # Only one message stored
        assert EmailMessage.objects.filter(message_id='<test-msg-123@example.com>').count() == 1

    def test_webhook_signature_verification(self, client, mailgun_payload):
        """Test that signature verification works."""
        api_key = 'test-api-key-12345'
        mailgun_payload['signature'] = compute_signature(
            api_key,
            mailgun_payload['timestamp'],
            mailgun_payload['token']
        )

        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = api_key

            response = client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )

        assert response.status_code == 200
        assert response.json()['status'] == 'queued'

    def test_webhook_invalid_signature(self, client, mailgun_payload):
        """Test that invalid signatures are rejected."""
        mailgun_payload['signature'] = 'invalid-signature'

        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = 'test-api-key-12345'

            response = client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )

        assert response.status_code == 401

    def test_webhook_stores_raw_post_data(self, client, mailgun_payload):
        """Test that raw POST data is stored for debugging."""
        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = None

            client.post(
                '/api/email/inbound/',
                data=encode_form_data(mailgun_payload),
                content_type='application/x-www-form-urlencoded'
            )

        msg = EmailMessage.objects.get(message_id='<test-msg-123@example.com>')
        assert msg.raw_post_data['sender'] == 'sender@example.com'
        assert msg.raw_post_data['subject'] == 'Test Email'
        assert msg.raw_post_data['Message-Id'] == '<test-msg-123@example.com>'

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/email/health/')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        assert response.json()['service'] == 'email_gateway'

    def test_webhook_saves_attachments(self, client, mailgun_payload):
        """Test that attachments are persisted and metadata stored."""
        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = None

            payload = dict(mailgun_payload)
            payload['attachment-count'] = '2'
            payload['content-id-map'] = json.dumps({
                "cid-1": ["attachment-1"],
                "cid-2": ["attachment-2"]
            })

            file1 = SimpleUploadedFile("note.txt", b"hello world", content_type="text/plain")
            file2 = SimpleUploadedFile("image.png", b"\x89PNG\r\n", content_type="image/png")

            response = client.post(
                '/api/email/inbound/',
                data={
                    **payload,
                    "attachment-1": file1,
                    "attachment-2": file2,
                },
            )

        assert response.status_code == 200
        msg = EmailMessage.objects.get(message_id=payload['Message-Id'])
        attachments = list(msg.stored_attachments.all())
        assert len(attachments) == 2
        filenames = sorted([a.filename for a in attachments])
        assert filenames == ["image.png", "note.txt"]
        content_ids = sorted([a.content_id for a in attachments])
        assert content_ids == ["cid-1", "cid-2"]

        # Metadata persisted on EmailMessage
        assert len(msg.attachments) == 2
        assert {m["filename"] for m in msg.attachments} == {"note.txt", "image.png"}
        # Files saved to storage
        for attachment in attachments:
            assert attachment.file
            assert attachment.file.name
            assert attachment.size > 0

    def test_webhook_duplicate_with_attachments(self, client, mailgun_payload):
        """Duplicate messages should not create duplicate attachments."""
        with patch('email_gateway.api.settings') as mock_settings:
            mock_settings.MAILGUN_API_KEY = None

            payload = dict(mailgun_payload)
            payload['attachment-count'] = '1'
            file1 = SimpleUploadedFile("note.txt", b"hello world", content_type="text/plain")

            response1 = client.post(
                '/api/email/inbound/',
                data={**payload, "attachment-1": file1},
            )
            assert response1.status_code == 200

            # Second request with same Message-Id should be duplicate
            file2 = SimpleUploadedFile("note.txt", b"hello again", content_type="text/plain")
            response2 = client.post(
                '/api/email/inbound/',
                data={**payload, "attachment-1": file2},
            )
            assert response2.status_code == 200
            assert response2.json()['status'] == 'duplicate'

        msg = EmailMessage.objects.get(message_id=payload['Message-Id'])
        # Only one attachment saved
        assert EmailAttachment.objects.filter(email_message=msg).count() == 1
