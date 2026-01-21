"""
API endpoints for event triggers.
"""

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from accounts.utils import require_organization as _require_organization

from .models import EventTrigger, EventTriggerRun, EventType
from .schemas import (
    EventTriggerCreate,
    EventTriggerResponse,
    EventTriggerRunResponse,
    EventTriggerUpdate,
    EventTypeInfo,
    EventTypesResponse,
    ManualDispatchRequest,
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


def _run_to_response(run: EventTriggerRun) -> EventTriggerRunResponse:
    """Convert an EventTriggerRun to response schema."""
    return EventTriggerRunResponse(
        id=run.id,
        run_id=str(run.run_id),
        trigger_id=run.trigger_id,
        trigger_name=run.trigger.name,
        source_type=run.source_type,
        source_id=run.source_id,
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


@router.post("/triggers/{trigger_id}/dispatch", response=EventTriggerRunResponse)
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
    run = EventTriggerRun.objects.create(
        organization=trigger.organization,
        trigger=trigger,
        source_type="documents_selection",
        source_id=data.document_ids[0],
        inputs=event_data,
        status=EventTriggerRun.Status.PENDING,
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
    run = EventTriggerRun.objects.select_related("trigger").get(id=run.id)

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
            "workspace_id": doc.workspace_id,
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


@router.get("/triggers/{trigger_id}/runs", response=list[EventTriggerRunResponse])
def list_trigger_runs(request, trigger_id: int, limit: int = 50):
    """List runs for a specific trigger."""
    organization = require_organization(request.user)

    trigger = get_object_or_404(
        EventTrigger, id=trigger_id, organization=organization
    )

    runs = EventTriggerRun.objects.filter(
        trigger=trigger
    ).select_related("trigger").order_by("-created_at")[:limit]

    return [_run_to_response(r) for r in runs]


@router.get("/runs", response=list[EventTriggerRunResponse])
def list_runs(
    request,
    status: str | None = None,
    project_id: int | None = None,
    limit: int = 50,
):
    """List trigger runs for the organization, optionally filtered by project."""
    organization = require_organization(request.user)

    queryset = EventTriggerRun.objects.filter(
        organization=organization
    ).select_related("trigger", "trigger__project").order_by("-created_at")

    if status:
        queryset = queryset.filter(status=status)

    if project_id is not None:
        queryset = queryset.filter(trigger__project_id=project_id)

    return [_run_to_response(r) for r in queryset[:limit]]


@router.get("/runs/{run_id}", response=EventTriggerRunResponse)
def get_run(request, run_id: str):
    """Get a specific trigger run by run_id."""
    organization = require_organization(request.user)

    run = get_object_or_404(
        EventTriggerRun.objects.select_related("trigger"),
        run_id=run_id,
        organization=organization,
    )

    return _run_to_response(run)
