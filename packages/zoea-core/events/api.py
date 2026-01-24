"""
API endpoints for event triggers and scheduled events.
"""

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import require_organization as _require_organization

from execution.models import ExecutionRun

from .models import EventTrigger, EventType, ScheduledEvent, ScheduleType
from .schemas import (
    ExecutionRunResponse,
    EventTriggerCreate,
    EventTriggerResponse,
    EventTriggerUpdate,
    EventTypeInfo,
    EventTypesResponse,
    ManualDispatchRequest,
    ScheduledEventCreate,
    ScheduledEventResponse,
    ScheduledEventUpdate,
    ScheduleTypeInfo,
    ScheduleTypesResponse,
)

router = Router(tags=["Events"])


def require_organization(user):
    """
    Get organization or raise HttpError.

    Wraps accounts.utils.require_organization to convert ValueError to HttpError
    for proper API error responses.
    """
    try:
        return _require_organization(user)
    except ValueError as e:
        raise HttpError(403, str(e))


def _trigger_to_response(trigger: EventTrigger) -> EventTriggerResponse:
    """Convert an EventTrigger to response schema."""
    return EventTriggerResponse(
        id=trigger.id,
        name=trigger.name,
        description=trigger.description,
        event_type=trigger.event_type,
        skills=trigger.skills or [],
        skill_count=trigger.skill_count,
        project_id=trigger.project_id,
        project_name=trigger.project.name if trigger.project else None,
        is_enabled=trigger.is_enabled,
        run_async=trigger.run_async,
        filters=trigger.filters or {},
        agent_config=trigger.agent_config or {},
        created_at=trigger.created_at,
        updated_at=trigger.updated_at,
        created_by_id=trigger.created_by_id,
    )


def _run_to_response(run: ExecutionRun) -> ExecutionRunResponse:
    """Convert an ExecutionRun to response schema."""
    trigger_name = run.trigger.name if run.trigger else ""
    return ExecutionRunResponse(
        id=run.id,
        run_id=str(run.run_id),
        trigger_id=run.trigger_id or 0,
        trigger_name=trigger_name,
        source_type=run.source_type,
        source_id=run.source_id or 0,
        status=run.status,
        inputs=run.inputs or {},
        outputs=run.outputs,
        error=run.error,
        telemetry=run.telemetry,
        duration_seconds=run.duration_seconds,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/types", response=EventTypesResponse)
def list_event_types(request):
    """List available event types."""
    return EventTypesResponse(
        event_types=[
            EventTypeInfo(value=choice.value, label=choice.label)
            for choice in EventType
        ]
    )


@router.get("/triggers", response=list[EventTriggerResponse])
def list_triggers(request, project_id: int | None = None, event_type: str | None = None):
    """
    List event triggers for the user's organization.

    Optionally filter by project_id or event_type.
    """
    organization = require_organization(request.user)

    queryset = EventTrigger.objects.filter(
        organization=organization
    ).select_related("project")

    if project_id is not None:
        queryset = queryset.filter(project_id=project_id)

    if event_type:
        queryset = queryset.filter(event_type=event_type)

    return [_trigger_to_response(t) for t in queryset]


@router.post("/triggers", response=EventTriggerResponse)
def create_trigger(request, data: EventTriggerCreate):
    """Create a new event trigger."""
    organization = require_organization(request.user)

    # Validate event_type
    if data.event_type not in [e.value for e in EventType]:
        raise HttpError(400, f"Invalid event_type: {data.event_type}")

    # Validate project belongs to org if provided
    project = None
    if data.project_id:
        from projects.models import Project

        project = get_object_or_404(
            Project, id=data.project_id, organization=organization
        )

    trigger = EventTrigger.objects.create(
        organization=organization,
        project=project,
        name=data.name,
        description=data.description,
        event_type=data.event_type,
        skills=data.skills,
        is_enabled=data.is_enabled,
        run_async=data.run_async,
        filters=data.filters,
        agent_config=data.agent_config,
        created_by=request.user,
    )

    return _trigger_to_response(trigger)


@router.get("/triggers/{trigger_id}", response=EventTriggerResponse)
def get_trigger(request, trigger_id: int):
    """Get a specific event trigger."""
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger.objects.select_related("project"),
        id=trigger_id,
        organization=organization,
    )

    return _trigger_to_response(trigger)


@router.patch("/triggers/{trigger_id}", response=EventTriggerResponse)
def update_trigger(request, trigger_id: int, data: EventTriggerUpdate):
    """Update an event trigger."""
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger, id=trigger_id, organization=organization
    )

    # Update only provided fields
    update_fields = []

    if data.name is not None:
        trigger.name = data.name
        update_fields.append("name")

    if data.description is not None:
        trigger.description = data.description
        update_fields.append("description")

    if data.skills is not None:
        trigger.skills = data.skills
        update_fields.append("skills")

    if data.is_enabled is not None:
        trigger.is_enabled = data.is_enabled
        update_fields.append("is_enabled")

    if data.run_async is not None:
        trigger.run_async = data.run_async
        update_fields.append("run_async")

    if data.filters is not None:
        trigger.filters = data.filters
        update_fields.append("filters")

    if data.agent_config is not None:
        trigger.agent_config = data.agent_config
        update_fields.append("agent_config")

    if update_fields:
        update_fields.append("updated_at")
        trigger.save(update_fields=update_fields)

    # Refresh to get project relation
    trigger = EventTrigger.objects.select_related("project").get(id=trigger_id)

    return _trigger_to_response(trigger)


@router.delete("/triggers/{trigger_id}")
def delete_trigger(request, trigger_id: int):
    """Delete an event trigger."""
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger, id=trigger_id, organization=organization
    )

    trigger.delete()

    return {"success": True}


@router.post("/triggers/{trigger_id}/dispatch", response=ExecutionRunResponse)
def dispatch_trigger(request, trigger_id: int, data: ManualDispatchRequest):
    """
    Manually dispatch a trigger with specific document IDs.

    Used for DOCUMENTS_SELECTED events where the user chooses
    which documents to process and which workflow to run.
    """
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger.objects.select_related("project"),
        id=trigger_id,
        organization=organization,
        is_enabled=True,
    )

    # Validate this trigger supports manual dispatch
    if trigger.event_type != EventType.DOCUMENTS_SELECTED.value:
        raise HttpError(400, "This trigger does not support manual dispatch")

    # Validate documents belong to the organization
    from documents.models import Document

    documents = Document.objects.filter(
        id__in=data.document_ids,
        organization=organization,
    )

    if documents.count() != len(data.document_ids):
        raise HttpError(400, "Some documents not found or inaccessible")

    # Build event data with document information
    event_data = _build_documents_selected_event_data(documents, data.document_ids)

    # Create the run record
    run = ExecutionRun.objects.create(
        organization=trigger.organization,
        project=trigger.project,
        trigger=trigger,
        trigger_type=trigger.event_type,
        source_type="documents_selection",
        source_id=data.document_ids[0],
        input_envelope={
            "trigger_type": trigger.event_type,
            "source_type": "documents_selection",
            "source_id": data.document_ids[0],
            "payload": event_data,
        },
        inputs=event_data,
        status=ExecutionRun.Status.PENDING,
        created_by=request.user,
    )

    # Queue for execution
    if trigger.run_async:
        from django_q.tasks import async_task

        task_id = async_task(
            "events.tasks.execute_event_trigger",
            run.id,
            task_name=f"documents_selected_{str(run.run_id)[:8]}",
            timeout=600,
        )
        run.task_id = task_id
        run.save(update_fields=["task_id"])
    else:
        from .tasks import _execute_trigger_run

        _execute_trigger_run(run)

    # Refresh to get trigger relation for response
    run = ExecutionRun.objects.select_related("trigger").get(id=run.id)

    return _run_to_response(run)


def _build_documents_selected_event_data(documents, document_ids: list[int]) -> dict:
    """
    Build event_data for DOCUMENTS_SELECTED events.

    Includes document metadata to help skills understand what they're processing.
    """
    documents_info = []
    for doc in documents:
        doc_info = {
            "id": doc.id,
            "name": doc.name,
            "document_type": doc.__class__.__name__,
            "description": getattr(doc, "description", ""),
            "project_id": doc.project_id,
            "folder_id": getattr(doc, "folder_id", None),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

        # Include content preview for text documents
        if hasattr(doc, "content"):
            content = doc.content or ""
            doc_info["content_preview"] = content[:500] if len(content) > 500 else content

        documents_info.append(doc_info)

    return {
        "document_ids": document_ids,
        "document_count": len(document_ids),
        "documents": documents_info,
    }


@router.get("/triggers/{trigger_id}/runs", response=list[ExecutionRunResponse])
def list_trigger_runs(request, trigger_id: int, limit: int = 50):
    """List execution runs for a specific trigger."""
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger, id=trigger_id, organization=organization
    )

    runs = ExecutionRun.objects.filter(
        trigger=trigger
    ).select_related("trigger").order_by("-created_at")[:limit]

    return [_run_to_response(r) for r in runs]


@router.get("/runs", response=list[ExecutionRunResponse])
def list_runs(
    request,
    status: str | None = None,
    project_id: int | None = None,
    limit: int = 50,
):
    """List trigger execution runs for the organization, optionally filtered by project."""
    organization = require_organization(request.user)

    queryset = ExecutionRun.objects.filter(
        organization=organization,
        trigger_id__isnull=False,
    ).select_related("trigger", "project").order_by("-created_at")

    if status:
        queryset = queryset.filter(status=status)

    if project_id is not None:
        queryset = queryset.filter(project_id=project_id)

    return [_run_to_response(r) for r in queryset[:limit]]


@router.get("/runs/{run_id}", response=ExecutionRunResponse)
def get_run(request, run_id: str):
    """Get a specific trigger execution run by run_id."""
    organization = require_organization(request.user)

    run = get_object_or_404(
        ExecutionRun.objects.select_related("trigger"),
        run_id=run_id,
        organization=organization,
    )

    return _run_to_response(run)


# =============================================================================
# Scheduled Event Endpoints
# =============================================================================


def _scheduled_event_to_response(
    scheduled_event: ScheduledEvent,
) -> ScheduledEventResponse:
    """Convert a ScheduledEvent to response schema."""
    return ScheduledEventResponse(
        id=scheduled_event.id,
        name=scheduled_event.name,
        description=scheduled_event.description,
        trigger_id=scheduled_event.trigger_id,
        trigger_name=scheduled_event.trigger.name if scheduled_event.trigger else "",
        schedule_type=scheduled_event.schedule_type,
        scheduled_at=scheduled_event.scheduled_at,
        cron_expression=scheduled_event.cron_expression,
        timezone_name=scheduled_event.timezone_name,
        event_data=scheduled_event.event_data or {},
        is_enabled=scheduled_event.is_enabled,
        next_run_at=scheduled_event.next_run_at,
        last_run_at=scheduled_event.last_run_at,
        run_count=scheduled_event.run_count,
        created_at=scheduled_event.created_at,
        updated_at=scheduled_event.updated_at,
        created_by_id=scheduled_event.created_by_id,
    )


@router.get("/schedule-types", response=ScheduleTypesResponse)
def list_schedule_types(request):
    """List available schedule types."""
    return ScheduleTypesResponse(
        schedule_types=[
            ScheduleTypeInfo(value=choice.value, label=choice.label)
            for choice in ScheduleType
        ]
    )


@router.get("/scheduled", response=list[ScheduledEventResponse])
def list_scheduled_events(
    request,
    trigger_id: int | None = None,
    is_enabled: bool | None = None,
):
    """
    List scheduled events for the user's organization.

    Optionally filter by trigger_id or enabled status.
    """
    organization = require_organization(request.user)

    queryset = ScheduledEvent.objects.filter(
        organization=organization
    ).select_related("trigger")

    if trigger_id is not None:
        queryset = queryset.filter(trigger_id=trigger_id)

    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled)

    return [_scheduled_event_to_response(e) for e in queryset]


@router.post("/scheduled", response=ScheduledEventResponse)
def create_scheduled_event(request, data: ScheduledEventCreate):
    """Create a new scheduled event."""
    organization = require_organization(request.user)

    # Validate schedule_type
    if data.schedule_type not in [e.value for e in ScheduleType]:
        raise HttpError(400, f"Invalid schedule_type: {data.schedule_type}")

    # Validate trigger belongs to org
    trigger = get_object_or_404(
        EventTrigger, id=data.trigger_id, organization=organization
    )

    # Validate schedule configuration
    if data.schedule_type == ScheduleType.ONESHOT and not data.scheduled_at:
        raise HttpError(400, "One-shot events require scheduled_at")

    if data.schedule_type == ScheduleType.CRON and not data.cron_expression:
        raise HttpError(400, "Cron events require cron_expression")

    scheduled_event = ScheduledEvent.objects.create(
        organization=organization,
        trigger=trigger,
        name=data.name,
        description=data.description,
        schedule_type=data.schedule_type,
        scheduled_at=data.scheduled_at,
        cron_expression=data.cron_expression,
        timezone_name=data.timezone_name,
        event_data=data.event_data,
        is_enabled=data.is_enabled,
        created_by=request.user,
    )

    # Calculate initial next_run
    scheduled_event.calculate_next_run()

    # Register with Django-Q2 if enabled
    if scheduled_event.is_enabled:
        from .scheduler import ScheduledEventService

        ScheduledEventService.register_with_django_q(scheduled_event)

    # Refresh to get trigger relation
    scheduled_event = ScheduledEvent.objects.select_related("trigger").get(
        id=scheduled_event.id
    )

    return _scheduled_event_to_response(scheduled_event)


@router.get("/scheduled/{scheduled_event_id}", response=ScheduledEventResponse)
def get_scheduled_event(request, scheduled_event_id: int):
    """Get a specific scheduled event."""
    organization = require_organization(request.user)

    scheduled_event = get_object_or_404(
        ScheduledEvent.objects.select_related("trigger"),
        id=scheduled_event_id,
        organization=organization,
    )

    return _scheduled_event_to_response(scheduled_event)


@router.patch("/scheduled/{scheduled_event_id}", response=ScheduledEventResponse)
def update_scheduled_event(
    request, scheduled_event_id: int, data: ScheduledEventUpdate
):
    """Update a scheduled event."""
    organization = require_organization(request.user)

    scheduled_event = get_object_or_404(
        ScheduledEvent, id=scheduled_event_id, organization=organization
    )

    # Track if we need to re-register
    needs_reregister = False

    # Update only provided fields
    update_fields = []

    if data.name is not None:
        scheduled_event.name = data.name
        update_fields.append("name")

    if data.description is not None:
        scheduled_event.description = data.description
        update_fields.append("description")

    if data.scheduled_at is not None:
        scheduled_event.scheduled_at = data.scheduled_at
        update_fields.append("scheduled_at")
        needs_reregister = True

    if data.cron_expression is not None:
        scheduled_event.cron_expression = data.cron_expression
        update_fields.append("cron_expression")
        needs_reregister = True

    if data.timezone_name is not None:
        scheduled_event.timezone_name = data.timezone_name
        update_fields.append("timezone_name")
        needs_reregister = True

    if data.event_data is not None:
        scheduled_event.event_data = data.event_data
        update_fields.append("event_data")

    if data.is_enabled is not None:
        scheduled_event.is_enabled = data.is_enabled
        update_fields.append("is_enabled")
        needs_reregister = True

    if update_fields:
        update_fields.append("updated_at")
        scheduled_event.save(update_fields=update_fields)

    # Re-register with Django-Q2 if schedule changed
    if needs_reregister:
        from .scheduler import ScheduledEventService

        ScheduledEventService.unregister_from_django_q(scheduled_event)
        if scheduled_event.is_enabled:
            ScheduledEventService.register_with_django_q(scheduled_event)
        scheduled_event.calculate_next_run()

    # Refresh to get trigger relation
    scheduled_event = ScheduledEvent.objects.select_related("trigger").get(
        id=scheduled_event_id
    )

    return _scheduled_event_to_response(scheduled_event)


@router.delete("/scheduled/{scheduled_event_id}")
def delete_scheduled_event(request, scheduled_event_id: int):
    """Delete a scheduled event."""
    organization = require_organization(request.user)

    scheduled_event = get_object_or_404(
        ScheduledEvent, id=scheduled_event_id, organization=organization
    )

    # Unregister from Django-Q2
    from .scheduler import ScheduledEventService

    ScheduledEventService.unregister_from_django_q(scheduled_event)

    scheduled_event.delete()

    return {"success": True}


@router.post("/scheduled/{scheduled_event_id}/execute")
def execute_scheduled_event_now(request, scheduled_event_id: int):
    """
    Manually execute a scheduled event immediately.

    Useful for testing or one-off executions.
    """
    organization = require_organization(request.user)

    scheduled_event = get_object_or_404(
        ScheduledEvent.objects.select_related("trigger"),
        id=scheduled_event_id,
        organization=organization,
    )

    if not scheduled_event.trigger.is_enabled:
        raise HttpError(400, "Associated trigger is disabled")

    from .scheduler import ScheduledEventService

    result = ScheduledEventService.execute_scheduled_event(scheduled_event.id)

    return result
