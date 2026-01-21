"""
Background tasks for event trigger execution.

Uses Django-Q2 for async task execution.
"""

from __future__ import annotations

import asyncio
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _create_artifacts_collection(run, document_ids: list, trigger):
    """
    Create a DocumentCollection for artifacts created during skill execution.

    Args:
        run: EventTriggerRun instance
        document_ids: List of document IDs to add to the collection
        trigger: EventTrigger instance

    Returns:
        DocumentCollection instance or None
    """
    from django.contrib.contenttypes.models import ContentType

    from documents.models import (
        CollectionItemDirection,
        CollectionItemSourceChannel,
        CollectionType,
        Document,
        DocumentCollection,
        DocumentCollectionItem,
    )

    if not document_ids:
        return None

    # Get the organization and project from the trigger
    organization = run.organization
    project = trigger.project

    # Create the collection
    run_id_str = str(run.run_id)
    collection = DocumentCollection.objects.create(
        organization=organization,
        project=project,
        collection_type=CollectionType.ARTIFACT,
        name=f"Trigger Run: {trigger.name} ({run_id_str[:8]})",
        description=f"Artifacts created by {trigger.name} trigger on {run.created_at.strftime('%Y-%m-%d %H:%M')}",
        is_active=True,
    )

    # Get ContentType for Document
    doc_content_type = ContentType.objects.get_for_model(Document)

    # Fetch documents to get their details
    documents = Document.objects.select_subclasses().filter(id__in=document_ids)
    doc_map = {doc.id: doc for doc in documents}

    # Add each document to the collection
    for doc_id in document_ids:
        doc = doc_map.get(doc_id)

        # Build source metadata with document details for frontend display
        source_metadata = {
            "trigger_id": trigger.id,
            "trigger_name": trigger.name,
            "trigger_run_id": run.id,
            "run_id": str(run.run_id),
            "event_type": trigger.event_type,
            "type": "markdown",  # Default type for display
            "mime_type": "text/markdown",
        }

        if doc:
            source_metadata["title"] = doc.name
            source_metadata["document_id"] = doc.id
            source_metadata["document_type"] = doc.get_type_name()
            # Include content preview for markdown display
            if hasattr(doc, "content") and doc.content:
                # Truncate content for preview
                content = doc.content[:2000]
                if len(doc.content) > 2000:
                    content += "\n\n... (truncated)"
                source_metadata["content"] = content

        position = collection.reserve_position(CollectionItemDirection.RIGHT)
        DocumentCollectionItem.objects.create(
            collection=collection,
            position=position,
            direction_added=CollectionItemDirection.RIGHT,
            content_type=doc_content_type,
            object_id=str(doc_id),
            source_channel=CollectionItemSourceChannel.TOOL,
            source_metadata=source_metadata,
        )

    logger.info(
        f"Created artifacts collection {collection.id} with {len(document_ids)} documents "
        f"for trigger run {run.run_id}"
    )

    return collection


def _link_artifacts_to_conversation(run, artifacts_collection):
    """
    Link the artifacts collection to the associated conversation if one exists.

    For email_message sources, finds the conversation via the email thread.

    Args:
        run: EventTriggerRun instance
        artifacts_collection: DocumentCollection to link
    """
    if not artifacts_collection:
        return

    conversation = None

    # For email sources, find conversation via email thread
    if run.source_type == "email_message":
        try:
            from email_gateway.models import EmailMessage

            email_msg = EmailMessage.objects.select_related(
                "email_thread__conversation"
            ).get(id=run.source_id)

            if email_msg.email_thread and email_msg.email_thread.conversation:
                conversation = email_msg.email_thread.conversation
        except EmailMessage.DoesNotExist:
            logger.warning(
                f"EmailMessage {run.source_id} not found for trigger run {run.run_id}"
            )

    # Link artifacts to conversation if found and not already set
    if conversation and not conversation.artifacts:
        conversation.artifacts = artifacts_collection
        conversation.save(update_fields=["artifacts"])
        logger.info(
            f"Linked artifacts collection {artifacts_collection.id} to "
            f"conversation {conversation.id}"
        )


def execute_event_trigger(trigger_run_id: int) -> dict:
    """
    Background task for executing an event trigger.

    This is the entry point for Django-Q2 async task execution.

    Args:
        trigger_run_id: ID of the EventTriggerRun to execute

    Returns:
        Dict with execution results
    """
    from .models import EventTriggerRun

    try:
        run = EventTriggerRun.objects.select_related(
            "trigger", "organization"
        ).get(id=trigger_run_id)
    except EventTriggerRun.DoesNotExist:
        logger.error(f"EventTriggerRun {trigger_run_id} not found")
        return {"error": f"EventTriggerRun {trigger_run_id} not found"}

    try:
        _execute_trigger_run(run)
        return {
            "run_id": str(run.run_id),
            "status": run.status,
            "outputs": run.outputs,
        }
    except Exception as e:
        logger.error(
            f"Failed to execute trigger run {run.run_id}: {e}",
            exc_info=True,
        )
        return {
            "run_id": str(run.run_id),
            "status": "failed",
            "error": str(e),
        }


def _execute_trigger_run(run) -> None:
    """
    Execute the trigger run using SkillsAgentService.

    Args:
        run: EventTriggerRun instance to execute
    """
    from .models import EventTriggerRun

    # Update status to running
    run.status = EventTriggerRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])

    trigger = run.trigger

    # Validate trigger has skills configured
    if not trigger.skills:
        run.status = EventTriggerRun.Status.SKIPPED
        run.error = "No skills configured for trigger"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at", "updated_at"])
        logger.warning(f"Trigger {trigger.id} has no skills configured")
        return

    try:
        # Import here to avoid circular imports
        from chat.skills_agent_service import SkillsAgentService

        from events.harness import SkillExecutionHarness

        # Get project for LLM configuration
        project = trigger.project

        # Extract agent config
        agent_config = trigger.agent_config or {}
        max_steps = agent_config.get("max_steps", 10)
        custom_instructions = agent_config.get("instructions")
        use_harness = agent_config.get("use_harness", True)

        # Create execution harness for isolated execution
        harness = None
        if use_harness:
            allowed_domains = agent_config.get("allowed_external_domains", [])
            max_documents = agent_config.get("max_documents_per_run", 50)
            rate_limit = agent_config.get("rate_limit_per_domain", 10)

            harness = SkillExecutionHarness.from_trigger_run(
                run,
                allowed_external_domains=frozenset(allowed_domains)
                if allowed_domains
                else None,
                max_documents_per_run=max_documents,
                rate_limit_per_domain=rate_limit,
            )
            logger.debug(f"Created execution harness for run {run.run_id}")

        # Create the skills agent
        service = SkillsAgentService(
            project=project,
            skill_names=trigger.skills,
            max_steps=max_steps,
            custom_instructions=custom_instructions,
            harness=harness,
        )

        # Build context from run data
        context = {
            "trigger_name": trigger.name,
            "trigger_id": trigger.id,
            "run_id": str(run.run_id),
            "organization_id": run.organization_id,
        }

        if project:
            context["project_id"] = project.id
            context["project_name"] = project.name

        # Execute the agent
        response = asyncio.run(
            service.process(
                event_type=trigger.event_type,
                event_data=run.inputs,
                context=context,
            )
        )

        # Collect created document IDs from harness audit log
        created_doc_ids = []
        if harness and response.audit_log:
            for entry in response.audit_log.get("entries", []):
                if (
                    entry.get("operation") == "create"
                    and entry.get("model") == "Document"
                    and entry.get("allowed")
                ):
                    created_doc_ids.append(entry["object_id"])

        # Create artifacts collection if documents were created
        artifacts_collection = None
        if created_doc_ids:
            artifacts_collection = _create_artifacts_collection(
                run, created_doc_ids, trigger
            )

        # Update run with results
        run.status = EventTriggerRun.Status.COMPLETED
        run.outputs = {
            "response": response.response,
            "skills_used": response.skills_used,
            "tools_called": response.tools_called,
            "artifacts": [
                {
                    "type": a.type,
                    "path": a.path,
                    "title": a.title,
                    "mime_type": a.mime_type,
                }
                for a in response.artifacts
            ],
            "created_document_ids": created_doc_ids,
        }

        # Link artifacts collection
        if artifacts_collection:
            run.artifacts = artifacts_collection
            # Also link to conversation if this is from an email
            _link_artifacts_to_conversation(run, artifacts_collection)

        # Include audit log in telemetry if available
        telemetry = response.telemetry.copy() if response.telemetry else {}
        if response.audit_log:
            telemetry["audit_log"] = response.audit_log

        run.telemetry = telemetry
        run.completed_at = timezone.now()

        update_fields = [
            "status",
            "outputs",
            "telemetry",
            "completed_at",
            "updated_at",
        ]
        if artifacts_collection:
            update_fields.append("artifacts")

        run.save(update_fields=update_fields)

        logger.info(
            f"Successfully executed trigger run {run.run_id}, "
            f"skills={response.skills_used}, tools={response.tools_called}"
        )

    except Exception as e:
        # Update run with error
        run.status = EventTriggerRun.Status.FAILED
        run.error = str(e)
        run.completed_at = timezone.now()
        run.save(
            update_fields=["status", "error", "completed_at", "updated_at"]
        )

        logger.error(
            f"Trigger run {run.run_id} failed: {e}",
            exc_info=True,
        )
        raise


def retry_failed_trigger_runs(max_retries: int = 3) -> int:
    """
    Retry failed trigger runs.

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        Number of runs retried
    """
    from .models import EventTriggerRun

    # Find failed runs that haven't exceeded retry limit
    # Note: Would need to track retry count for full implementation
    failed_runs = EventTriggerRun.objects.filter(
        status=EventTriggerRun.Status.FAILED,
    ).select_related("trigger")[:50]

    retried = 0
    for run in failed_runs:
        if not run.trigger.is_enabled:
            continue

        # Reset status and re-queue
        run.status = EventTriggerRun.Status.PENDING
        run.error = None
        run.started_at = None
        run.completed_at = None
        run.save(
            update_fields=[
                "status",
                "error",
                "started_at",
                "completed_at",
                "updated_at",
            ]
        )

        if run.trigger.run_async:
            from django_q.tasks import async_task

            task_id = async_task(
                "events.tasks.execute_event_trigger",
                run.id,
                task_name=f"event_trigger_retry_{run.run_id[:8]}",
                timeout=600,
            )
            run.task_id = task_id
            run.save(update_fields=["task_id"])
        else:
            _execute_trigger_run(run)

        retried += 1

    logger.info(f"Retried {retried} failed trigger runs")
    return retried
