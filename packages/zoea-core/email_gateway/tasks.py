"""
Background tasks for email processing.

These tasks handle asynchronous processing of inbound emails.
In development, tasks run immediately (synchronously).
In production, configure a proper task backend (Redis, database, etc.).
"""

import logging

from .services import EmailProcessingService, EmailProcessingError

logger = logging.getLogger(__name__)


def process_email_message(email_message_id: int) -> bool:
    """
    Background task to process a queued email message.

    This task:
    1. Validates the sender and finds their organization
    2. Resolves the email thread (RFC 2822 threading)
    3. Creates/updates EmailThread and Conversation
    4. Creates a chat Message for the email content

    Args:
        email_message_id: ID of the EmailMessage to process

    Returns:
        True if processing succeeded, False otherwise
    """
    logger.info(f"Processing email message {email_message_id}")

    service = EmailProcessingService()
    try:
        result = service.process_email(email_message_id)
        if result:
            logger.info(f"Successfully processed email message {email_message_id}")
        else:
            logger.warning(f"Email message {email_message_id} was not processed (already done?)")
        return result
    except EmailProcessingError as e:
        logger.error(f"Failed to process email message {email_message_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error processing email message {email_message_id}: {e}")
        return False


def process_pending_emails() -> int:
    """
    Process all pending email messages.

    This can be called via management command or scheduled task
    to process any emails that may have failed to enqueue.

    Returns:
        Number of emails processed
    """
    from .models import EmailMessage

    pending = EmailMessage.objects.filter(status__in=['received', 'queued'])
    processed_count = 0

    for email_msg in pending:
        try:
            if process_email_message(email_msg.id):
                processed_count += 1
        except Exception as e:
            logger.error(f"Error processing email {email_msg.id}: {e}")

    logger.info(f"Processed {processed_count} pending emails")
    return processed_count


def retry_failed_emails(max_retries: int = 3) -> int:
    """
    Retry processing failed email messages.

    Args:
        max_retries: Maximum number of times to retry

    Returns:
        Number of emails successfully reprocessed
    """
    from .models import EmailMessage

    failed = EmailMessage.objects.filter(status='failed')
    reprocessed_count = 0

    for email_msg in failed:
        # Reset status to allow reprocessing
        email_msg.status = 'queued'
        email_msg.error_message = ''
        email_msg.save(update_fields=['status', 'error_message'])

        try:
            if process_email_message(email_msg.id):
                reprocessed_count += 1
        except Exception as e:
            logger.error(f"Retry failed for email {email_msg.id}: {e}")

    logger.info(f"Reprocessed {reprocessed_count} failed emails")
    return reprocessed_count
