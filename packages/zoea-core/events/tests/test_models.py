"""
Tests for event trigger models.
"""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from events.models import EventTrigger, EventType, ScheduledEvent, ScheduleType
from execution.models import ExecutionRun
from projects.models import Project

User = get_user_model()


@pytest.fixture
def organization():
    """Create a test organization."""
    return Account.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def user(organization):
    """Create a test user."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    organization.add_user(user)
    return user


@pytest.fixture
def project(organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/test",
        created_by=user,
    )


@pytest.mark.django_db
class TestEventTrigger:
    """Tests for EventTrigger model."""

    def test_create_trigger(self, organization, user):
        """Test creating an event trigger."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Test Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["extract-data", "send-webhook"],
            created_by=user,
        )

        assert trigger.id is not None
        assert trigger.name == "Test Trigger"
        assert trigger.event_type == EventType.EMAIL_RECEIVED
        assert trigger.skills == ["extract-data", "send-webhook"]
        assert trigger.skill_count == 2
        assert trigger.is_enabled is True
        assert trigger.run_async is True

    def test_create_project_scoped_trigger(self, organization, project, user):
        """Test creating a project-scoped trigger."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            project=project,
            name="Project Trigger",
            event_type=EventType.DOCUMENT_CREATED,
            skills=["analyze-document"],
            created_by=user,
        )

        assert trigger.project == project
        assert str(trigger) == f"Project Trigger ({EventType.DOCUMENT_CREATED}) - {project.name}"

    def test_trigger_str_org_wide(self, organization, user):
        """Test string representation for org-wide trigger."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Org Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["test"],
            created_by=user,
        )

        assert "org-wide" in str(trigger)


@pytest.mark.django_db
class TestExecutionRun:
    """Tests for ExecutionRun model."""

    def test_create_run(self, organization, user):
        """Test creating a trigger run."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Test Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["test"],
            created_by=user,
        )

        run = ExecutionRun.objects.create(
            organization=organization,
            trigger=trigger,
            trigger_type=trigger.event_type,
            source_type="email_message",
            source_id=123,
            inputs={"subject": "Test", "body": "Hello"},
        )

        assert run.id is not None
        assert run.run_id is not None
        assert run.status == ExecutionRun.Status.PENDING
        assert run.source_type == "email_message"
        assert run.source_id == 123
        assert run.inputs == {"subject": "Test", "body": "Hello"}

    def test_run_status_choices(self, organization, user):
        """Test run status choices."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Test Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["test"],
            created_by=user,
        )

        run = ExecutionRun.objects.create(
            organization=organization,
            trigger=trigger,
            trigger_type=trigger.event_type,
            source_type="document",
            source_id=1,
        )

        # Test all statuses
        for status in ExecutionRun.Status:
            run.status = status
            run.save()
            run.refresh_from_db()
            assert run.status == status

    def test_duration_seconds(self, organization, user):
        """Test duration calculation."""
        from django.utils import timezone
        from datetime import timedelta

        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Test Trigger",
            event_type=EventType.EMAIL_RECEIVED,
            skills=["test"],
            created_by=user,
        )

        run = ExecutionRun.objects.create(
            organization=organization,
            trigger=trigger,
            trigger_type=trigger.event_type,
            source_type="test",
            source_id=1,
        )

        # No duration when not started
        assert run.duration_seconds is None

        # Set timing
        run.started_at = timezone.now()
        run.completed_at = run.started_at + timedelta(seconds=5.5)
        run.save()

        assert run.duration_seconds == pytest.approx(5.5, rel=0.1)


@pytest.mark.django_db
class TestEventType:
    """Tests for EventType enum."""

    def test_event_types(self):
        """Test all event types are defined."""
        assert EventType.EMAIL_RECEIVED == "email_received"
        assert EventType.DOCUMENT_CREATED == "document_created"
        assert EventType.DOCUMENT_UPDATED == "document_updated"

    def test_scheduled_event_types(self):
        """Test scheduled event types are defined."""
        assert EventType.SCHEDULED_ONESHOT == "scheduled_oneshot"
        assert EventType.SCHEDULED_CRON == "scheduled_cron"


@pytest.mark.django_db
class TestScheduledEvent:
    """Tests for ScheduledEvent model."""

    @pytest.fixture
    def trigger(self, organization, user):
        """Create a test event trigger."""
        return EventTrigger.objects.create(
            organization=organization,
            name="Test Trigger",
            event_type=EventType.SCHEDULED_CRON,
            skills=["daily-report"],
            created_by=user,
        )

    def test_create_oneshot_scheduled_event(self, organization, trigger, user):
        """Test creating a one-shot scheduled event."""
        from django.utils import timezone
        from datetime import timedelta

        scheduled_at = timezone.now() + timedelta(hours=1)

        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="One-Time Report",
            schedule_type=ScheduleType.ONESHOT,
            scheduled_at=scheduled_at,
            event_data={"report_type": "monthly"},
            created_by=user,
        )

        assert scheduled_event.id is not None
        assert scheduled_event.name == "One-Time Report"
        assert scheduled_event.schedule_type == ScheduleType.ONESHOT
        assert scheduled_event.scheduled_at == scheduled_at
        assert scheduled_event.is_enabled is True
        assert scheduled_event.run_count == 0
        assert scheduled_event.event_data == {"report_type": "monthly"}

    def test_create_cron_scheduled_event(self, organization, trigger, user):
        """Test creating a cron scheduled event."""
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Daily Report",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * 1-5",
            timezone_name="America/New_York",
            created_by=user,
        )

        assert scheduled_event.id is not None
        assert scheduled_event.name == "Daily Report"
        assert scheduled_event.schedule_type == ScheduleType.CRON
        assert scheduled_event.cron_expression == "0 9 * * 1-5"
        assert scheduled_event.timezone_name == "America/New_York"

    def test_scheduled_event_str_oneshot(self, organization, trigger, user):
        """Test string representation for one-shot event."""
        from django.utils import timezone

        scheduled_at = timezone.now()
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Test Event",
            schedule_type=ScheduleType.ONESHOT,
            scheduled_at=scheduled_at,
            created_by=user,
        )

        assert "oneshot" in str(scheduled_event).lower()
        assert "Test Event" in str(scheduled_event)

    def test_scheduled_event_str_cron(self, organization, trigger, user):
        """Test string representation for cron event."""
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Cron Event",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            created_by=user,
        )

        assert "cron" in str(scheduled_event).lower()
        assert "0 9 * * *" in str(scheduled_event)

    def test_record_execution(self, organization, trigger, user):
        """Test recording execution updates run count and last_run_at."""
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Test Event",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            created_by=user,
        )

        assert scheduled_event.run_count == 0
        assert scheduled_event.last_run_at is None

        scheduled_event.record_execution()
        scheduled_event.refresh_from_db()

        assert scheduled_event.run_count == 1
        assert scheduled_event.last_run_at is not None

    def test_calculate_next_run_oneshot_future(self, organization, trigger, user):
        """Test next_run calculation for future one-shot event."""
        from django.utils import timezone
        from datetime import timedelta

        scheduled_at = timezone.now() + timedelta(hours=1)

        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Future Event",
            schedule_type=ScheduleType.ONESHOT,
            scheduled_at=scheduled_at,
            created_by=user,
        )

        scheduled_event.calculate_next_run()
        scheduled_event.refresh_from_db()

        assert scheduled_event.next_run_at == scheduled_at

    def test_calculate_next_run_oneshot_past(self, organization, trigger, user):
        """Test next_run calculation for past one-shot event."""
        from django.utils import timezone
        from datetime import timedelta

        scheduled_at = timezone.now() - timedelta(hours=1)

        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Past Event",
            schedule_type=ScheduleType.ONESHOT,
            scheduled_at=scheduled_at,
            created_by=user,
        )

        scheduled_event.calculate_next_run()
        scheduled_event.refresh_from_db()

        assert scheduled_event.next_run_at is None

    def test_calculate_next_run_cron(self, organization, trigger, user):
        """Test next_run calculation for cron event."""
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Cron Event",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            created_by=user,
        )

        scheduled_event.calculate_next_run()
        scheduled_event.refresh_from_db()

        # Should have a next_run in the future
        from django.utils import timezone

        assert scheduled_event.next_run_at is not None
        assert scheduled_event.next_run_at > timezone.now()

    def test_calculate_next_run_disabled(self, organization, trigger, user):
        """Test next_run is None for disabled event."""
        scheduled_event = ScheduledEvent.objects.create(
            organization=organization,
            trigger=trigger,
            name="Disabled Event",
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            is_enabled=False,
            created_by=user,
        )

        scheduled_event.calculate_next_run()
        scheduled_event.refresh_from_db()

        assert scheduled_event.next_run_at is None
