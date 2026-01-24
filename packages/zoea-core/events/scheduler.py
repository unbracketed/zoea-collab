"""
Scheduled event management via Django-Q2.

Provides services for:
- Registering scheduled events with Django-Q2
- Executing scheduled events
- Managing cron schedules
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from .models import ScheduledEvent

logger = logging.getLogger(__name__)


class ScheduledEventService:
    """
    Service for managing scheduled event execution.

    Uses Django-Q2 for task scheduling and execution:
    - One-shot events are scheduled as delayed tasks
    - Cron events are registered as Django-Q2 schedules
    """

    @staticmethod
    def execute_scheduled_event(scheduled_event_id: int) -> dict:
        """
        Execute a scheduled event.

        This is the task function called by Django-Q2 when a schedule fires.

        Args:
            scheduled_event_id: ID of the ScheduledEvent to execute.

        Returns:
            Dict with execution result including any error messages.
        """
        from .dispatcher import dispatch_event
        from .models import EventType, ScheduledEvent, ScheduleType

        try:
            scheduled_event = ScheduledEvent.objects.select_related(
                "trigger", "organization"
            ).get(id=scheduled_event_id)
        except ScheduledEvent.DoesNotExist:
            logger.error(f"ScheduledEvent {scheduled_event_id} not found")
            return {"success": False, "error": "Scheduled event not found"}

        if not scheduled_event.is_enabled:
            logger.info(f"ScheduledEvent {scheduled_event_id} is disabled, skipping")
            return {"success": False, "error": "Scheduled event is disabled"}

        if not scheduled_event.trigger.is_enabled:
            logger.info(
                f"Trigger for ScheduledEvent {scheduled_event_id} is disabled, skipping"
            )
            return {"success": False, "error": "Associated trigger is disabled"}

        # Determine event type based on schedule type
        event_type = (
            EventType.SCHEDULED_CRON
            if scheduled_event.schedule_type == ScheduleType.CRON
            else EventType.SCHEDULED_ONESHOT
        )

        # Build event data
        event_data = {
            "scheduled_event_id": scheduled_event.id,
            "scheduled_event_name": scheduled_event.name,
            "schedule_type": scheduled_event.schedule_type,
            "run_count": scheduled_event.run_count + 1,
            **scheduled_event.event_data,
        }

        try:
            # Dispatch the event to the trigger
            dispatch_event(
                event_type=event_type,
                organization=scheduled_event.organization,
                project=scheduled_event.trigger.project,
                event_data=event_data,
                trigger_id=scheduled_event.trigger.id,
            )

            # Record execution
            scheduled_event.record_execution()

            # Calculate next run for cron events
            if scheduled_event.schedule_type == ScheduleType.CRON:
                scheduled_event.calculate_next_run()

            logger.info(
                f"Successfully executed ScheduledEvent {scheduled_event_id} "
                f"({scheduled_event.name})"
            )

            return {
                "success": True,
                "scheduled_event_id": scheduled_event_id,
                "trigger_id": scheduled_event.trigger.id,
            }

        except Exception as e:
            logger.exception(
                f"Error executing ScheduledEvent {scheduled_event_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    @classmethod
    def register_with_django_q(cls, scheduled_event: ScheduledEvent) -> bool:
        """
        Register a scheduled event with Django-Q2.

        For one-shot events, schedules a delayed task.
        For cron events, creates a Django-Q2 Schedule.

        Args:
            scheduled_event: The ScheduledEvent to register.

        Returns:
            True if registration succeeded, False otherwise.
        """
        from .models import ScheduleType

        try:
            from django_q.tasks import async_task, schedule
            from django_q.models import Schedule
        except ImportError:
            logger.warning("Django-Q2 not installed, cannot register schedule")
            return False

        if not scheduled_event.is_enabled:
            logger.info(
                f"ScheduledEvent {scheduled_event.id} is disabled, not registering"
            )
            return False

        if scheduled_event.schedule_type == ScheduleType.ONESHOT:
            return cls._register_oneshot(scheduled_event)
        elif scheduled_event.schedule_type == ScheduleType.CRON:
            return cls._register_cron(scheduled_event)
        else:
            logger.error(f"Unknown schedule type: {scheduled_event.schedule_type}")
            return False

    @classmethod
    def _register_oneshot(cls, scheduled_event: ScheduledEvent) -> bool:
        """Register a one-shot scheduled event."""
        from django_q.tasks import async_task

        if not scheduled_event.scheduled_at:
            logger.error(
                f"One-shot ScheduledEvent {scheduled_event.id} has no scheduled_at"
            )
            return False

        if scheduled_event.scheduled_at <= timezone.now():
            logger.warning(
                f"One-shot ScheduledEvent {scheduled_event.id} is in the past"
            )
            return False

        # Schedule as delayed task
        task_id = async_task(
            "events.scheduler.ScheduledEventService.execute_scheduled_event",
            scheduled_event.id,
            task_name=f"scheduled_event_{scheduled_event.id}",
            hook=None,
            schedule=scheduled_event.scheduled_at,
        )

        logger.info(
            f"Registered one-shot ScheduledEvent {scheduled_event.id} "
            f"as task {task_id} for {scheduled_event.scheduled_at}"
        )

        # Update next_run_at
        scheduled_event.next_run_at = scheduled_event.scheduled_at
        scheduled_event.save(update_fields=["next_run_at"])

        return True

    @classmethod
    def _register_cron(cls, scheduled_event: ScheduledEvent) -> bool:
        """Register a cron scheduled event."""
        from django_q.models import Schedule

        if not scheduled_event.cron_expression:
            logger.error(
                f"Cron ScheduledEvent {scheduled_event.id} has no cron_expression"
            )
            return False

        schedule_name = f"scheduled_event_{scheduled_event.id}"

        # Remove existing schedule if any
        Schedule.objects.filter(name=schedule_name).delete()

        # Create new schedule
        schedule = Schedule.objects.create(
            name=schedule_name,
            func="events.scheduler.ScheduledEventService.execute_scheduled_event",
            args=str(scheduled_event.id),
            schedule_type=Schedule.CRON,
            cron=scheduled_event.cron_expression,
        )

        # Store schedule ID
        scheduled_event.django_q_schedule_id = schedule_name
        scheduled_event.calculate_next_run()

        logger.info(
            f"Registered cron ScheduledEvent {scheduled_event.id} "
            f"with expression '{scheduled_event.cron_expression}'"
        )

        return True

    @classmethod
    def unregister_from_django_q(cls, scheduled_event: ScheduledEvent) -> bool:
        """
        Unregister a scheduled event from Django-Q2.

        Args:
            scheduled_event: The ScheduledEvent to unregister.

        Returns:
            True if unregistration succeeded, False otherwise.
        """
        try:
            from django_q.models import Schedule
        except ImportError:
            logger.warning("Django-Q2 not installed")
            return False

        from .models import ScheduleType

        if scheduled_event.schedule_type == ScheduleType.CRON:
            schedule_name = f"scheduled_event_{scheduled_event.id}"
            deleted, _ = Schedule.objects.filter(name=schedule_name).delete()
            if deleted:
                logger.info(
                    f"Unregistered cron ScheduledEvent {scheduled_event.id}"
                )
                scheduled_event.django_q_schedule_id = ""
                scheduled_event.next_run_at = None
                scheduled_event.save(
                    update_fields=["django_q_schedule_id", "next_run_at"]
                )
            return deleted > 0

        # One-shot tasks are harder to cancel; just clear next_run
        scheduled_event.next_run_at = None
        scheduled_event.save(update_fields=["next_run_at"])
        return True


def get_due_scheduled_events():
    """
    Get all scheduled events that are due to run.

    Returns events where:
    - is_enabled is True
    - next_run_at is not None and <= now

    This can be used by a polling mechanism if Django-Q2 is not available.
    """
    from .models import ScheduledEvent

    return ScheduledEvent.objects.filter(
        is_enabled=True,
        next_run_at__isnull=False,
        next_run_at__lte=timezone.now(),
    ).select_related("trigger", "organization")


def run_due_scheduled_events():
    """
    Execute all due scheduled events.

    This is a fallback polling mechanism for when Django-Q2 is not running.
    Can be called from a management command or cron job.
    """
    due_events = get_due_scheduled_events()
    results = []

    for event in due_events:
        result = ScheduledEventService.execute_scheduled_event(event.id)
        results.append({"scheduled_event_id": event.id, **result})

    return results
