"""
Event dispatcher for routing events to matching triggers.

Finds EventTriggers that match incoming events and dispatches them
to the SkillsAgentService for execution.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from execution.models import ExecutionRun

from .models import EventTrigger, EventType

if TYPE_CHECKING:
    from organizations.models import Organization
    from projects.models import Project

logger = logging.getLogger(__name__)


class EventDispatcher:
    """
    Central event dispatcher for routing events to triggers.

    Responsibilities:
    1. Find matching EventTriggers for an event
    2. Apply event filters
    3. Create ExecutionRun records
    4. Dispatch to SkillsAgentService (sync or async)
    """

    def dispatch(
        self,
        event_type: str | EventType,
        source_type: str,
        source_id: int,
        event_data: dict[str, Any],
        organization: Organization,
        project: Project | None = None,
        user=None,
    ) -> list[ExecutionRun]:
        """
        Dispatch an event to all matching triggers.

        Args:
            event_type: Type of event (EventType enum or string)
            source_type: Type of source object (e.g., "email_message", "document")
            source_id: ID of the source object
            event_data: Event payload data
            organization: Organization scope for the event
            project: Optional project scope for the event
            user: Optional user who initiated the event

        Returns:
            List of ExecutionRun records created for matching triggers
        """
        if isinstance(event_type, EventType):
            event_type = event_type.value

        logger.info(
            f"Dispatching event: type={event_type}, source={source_type}:{source_id}, "
            f"org={organization.id}, project={project.id if project else None}"
        )

        # Find matching triggers
        triggers = self._find_matching_triggers(
            event_type=event_type,
            organization=organization,
            project=project,
            event_data=event_data,
        )

        if not triggers:
            logger.debug(f"No triggers found for event {event_type}")
            return []

        logger.info(f"Found {len(triggers)} matching triggers for event {event_type}")

        # Create runs and dispatch
        runs: list[ExecutionRun] = []
        for trigger in triggers:
            try:
                run = self._dispatch_trigger(
                    trigger=trigger,
                    source_type=source_type,
                    source_id=source_id,
                    event_data=event_data,
                )
                runs.append(run)
            except Exception as e:
                logger.error(
                    f"Failed to dispatch trigger {trigger.id}: {e}",
                    exc_info=True,
                )

        return runs

    def _find_matching_triggers(
        self,
        event_type: str,
        organization: Organization,
        project: Project | None,
        event_data: dict[str, Any],
    ) -> list[EventTrigger]:
        """
        Find all enabled triggers matching the event.

        Matching rules:
        1. Must match event_type
        2. Must belong to the organization
        3. Project-scoped triggers only match events from that project
        4. Org-wide triggers (no project) match all events in the org
        5. Must pass any configured filters
        """
        # Base query: enabled triggers for this org and event type
        queryset = EventTrigger.objects.filter(
            organization=organization,
            event_type=event_type,
            is_enabled=True,
        )

        # Get org-wide triggers (project is null)
        org_wide_triggers = queryset.filter(project__isnull=True)

        # Get project-specific triggers if project is provided
        project_triggers = (
            queryset.filter(project=project) if project else EventTrigger.objects.none()
        )

        # Combine both querysets
        all_triggers = list(org_wide_triggers) + list(project_triggers)

        # Apply filters
        matching_triggers = []
        for trigger in all_triggers:
            if self._matches_filters(trigger, event_data):
                matching_triggers.append(trigger)
            else:
                logger.debug(
                    f"Trigger {trigger.id} skipped due to filter mismatch"
                )

        return matching_triggers

    def _matches_filters(
        self,
        trigger: EventTrigger,
        event_data: dict[str, Any],
    ) -> bool:
        """
        Check if event data matches trigger filters.

        Filters support simple key-value matching:
        {"document_type": "markdown"} matches if event_data["document_type"] == "markdown"

        Empty filters always match.
        """
        if not trigger.filters:
            return True

        for key, expected_value in trigger.filters.items():
            actual_value = event_data.get(key)

            if isinstance(expected_value, list):
                # List filter: actual value must be in list
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False

        return True

    def _dispatch_trigger(
        self,
        trigger: EventTrigger,
        source_type: str,
        source_id: int,
        event_data: dict[str, Any],
    ) -> ExecutionRun:
        """
        Dispatch a single trigger, creating a run record.

        Args:
            trigger: The EventTrigger to execute
            source_type: Type of source object
            source_id: ID of the source object
            event_data: Event payload data

        Returns:
            ExecutionRun record
        """
        # Create the run record
        run = ExecutionRun.objects.create(
            organization=trigger.organization,
            project=trigger.project,
            trigger=trigger,
            trigger_type=trigger.event_type,
            source_type=source_type,
            source_id=source_id,
            input_envelope={
                "trigger_type": trigger.event_type,
                "source_type": source_type,
                "source_id": source_id,
                "payload": event_data,
            },
            inputs=event_data,
            status=ExecutionRun.Status.PENDING,
            created_by=trigger.created_by,
        )

        logger.info(
            f"Created ExecutionRun {run.run_id} for trigger {trigger.name}"
        )

        if trigger.run_async:
            self._queue_async_execution(run)
        else:
            self._execute_sync(run)

        return run

    def _queue_async_execution(self, run: ExecutionRun) -> None:
        """Queue trigger execution to background task."""
        from django_q.tasks import async_task

        task_id = async_task(
            "events.tasks.execute_event_trigger",
            run.id,
            task_name=f"event_trigger_{run.run_id[:8]}",
            timeout=600,  # 10 minute timeout
        )

        run.task_id = task_id
        run.save(update_fields=["task_id"])

        logger.info(f"Queued trigger run {run.run_id} as task {task_id}")

    def _execute_sync(self, run: ExecutionRun) -> None:
        """Execute trigger synchronously."""
        from .tasks import _execute_trigger_run

        try:
            _execute_trigger_run(run)
        except Exception as e:
            logger.error(
                f"Sync execution failed for run {run.run_id}: {e}",
                exc_info=True,
            )


def dispatch_event(
    event_type: str | EventType,
    source_type: str,
    source_id: int,
    event_data: dict[str, Any],
    organization,
    project=None,
    user=None,
) -> list[ExecutionRun]:
    """
    Convenience function for dispatching events.

    This is the main entry point for event dispatching from other modules.

    Example:
        from events.dispatcher import dispatch_event
        from events.models import EventType

        dispatch_event(
            event_type=EventType.EMAIL_RECEIVED,
            source_type="email_message",
            source_id=email_msg.id,
            event_data={"subject": email_msg.subject, ...},
            organization=organization,
            project=project,
        )
    """
    dispatcher = EventDispatcher()
    return dispatcher.dispatch(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        event_data=event_data,
        organization=organization,
        project=project,
        user=user,
    )
