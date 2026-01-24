"""Tests for output_dispatch models."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from events.models import EventTrigger, EventType
from output_dispatch.models import (
    DestinationType,
    DispatchLog,
    DispatchStatus,
    OutputRoute,
)
from projects.models import Project

User = get_user_model()


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Account.objects.create(name="Test Organization", slug="test-org")


@pytest.fixture
def user(db, organization):
    """Create a test user."""
    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="testpass123",
    )
    return user


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/test-project",
        created_by=user,
    )


@pytest.fixture
def trigger(db, organization, user):
    """Create a test event trigger."""
    return EventTrigger.objects.create(
        organization=organization,
        name="Test Trigger",
        event_type=EventType.DOCUMENT_CREATED,
        skills=["test-skill"],
        created_by=user,
    )


@pytest.fixture
def output_route(db, organization, user):
    """Create a test output route."""
    return OutputRoute.objects.create(
        organization=organization,
        name="Test Webhook Route",
        destination_type=DestinationType.WEBHOOK,
        webhook_url="https://example.com/webhook",
        created_by=user,
    )


class TestOutputRoute:
    """Tests for OutputRoute model."""

    def test_create_route(self, organization, user):
        """Test creating an output route."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Test Route",
            destination_type=DestinationType.WEBHOOK,
            webhook_url="https://example.com/hook",
            created_by=user,
        )

        assert route.id is not None
        assert route.name == "Test Route"
        assert route.destination_type == DestinationType.WEBHOOK
        assert route.is_enabled is True
        assert route.priority == 0
        assert route.include_artifacts is True

    def test_create_slack_route(self, organization, user):
        """Test creating a Slack route."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Slack Route",
            destination_type=DestinationType.SLACK,
            channel_id="C12345",
            created_by=user,
        )

        assert route.destination_type == DestinationType.SLACK
        assert route.channel_id == "C12345"

    def test_create_trigger_scoped_route(self, organization, trigger, user):
        """Test creating a route scoped to a trigger."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Trigger Route",
            destination_type=DestinationType.WEBHOOK,
            trigger=trigger,
            webhook_url="https://example.com/hook",
            created_by=user,
        )

        assert route.trigger == trigger

    def test_create_project_scoped_route(self, organization, project, user):
        """Test creating a route scoped to a project."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Project Route",
            destination_type=DestinationType.WEBHOOK,
            project=project,
            webhook_url="https://example.com/hook",
            created_by=user,
        )

        assert route.project == project

    def test_matches_output_enabled(self, output_route):
        """Test that enabled route matches output."""
        assert output_route.matches_output({}) is True

    def test_matches_output_disabled(self, output_route):
        """Test that disabled route does not match output."""
        output_route.is_enabled = False
        output_route.save()

        assert output_route.matches_output({}) is False

    def test_matches_output_with_filter(self, organization, user):
        """Test route with output filter."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Filtered Route",
            destination_type=DestinationType.WEBHOOK,
            webhook_url="https://example.com/hook",
            output_filter={"status": "completed"},
            created_by=user,
        )

        assert route.matches_output({"status": "completed"}) is True
        assert route.matches_output({"status": "failed"}) is False
        assert route.matches_output({}) is False

    def test_matches_output_with_list_filter(self, organization, user):
        """Test route with list filter value."""
        route = OutputRoute.objects.create(
            organization=organization,
            name="Filtered Route",
            destination_type=DestinationType.WEBHOOK,
            webhook_url="https://example.com/hook",
            output_filter={"status": ["completed", "success"]},
            created_by=user,
        )

        assert route.matches_output({"status": "completed"}) is True
        assert route.matches_output({"status": "success"}) is True
        assert route.matches_output({"status": "failed"}) is False

    def test_string_representation(self, output_route):
        """Test string representation."""
        expected = "Test Webhook Route (Webhook)"
        assert str(output_route) == expected


class TestDispatchLog:
    """Tests for DispatchLog model."""

    def test_create_log(self, organization, output_route):
        """Test creating a dispatch log."""
        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        assert log.id is not None
        assert log.dispatch_id is not None
        assert log.status == DispatchStatus.PENDING
        assert log.retry_count == 0

    def test_set_status_sending(self, organization, output_route):
        """Test setting status to sending updates sent_at."""
        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        assert log.sent_at is None

        log.set_status(DispatchStatus.SENDING)
        log.refresh_from_db()

        assert log.status == DispatchStatus.SENDING
        assert log.sent_at is not None

    def test_set_status_success(self, organization, output_route):
        """Test setting status to success updates completed_at."""
        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        log.set_status(DispatchStatus.SUCCESS)
        log.refresh_from_db()

        assert log.status == DispatchStatus.SUCCESS
        assert log.completed_at is not None

    def test_set_status_failed(self, organization, output_route):
        """Test setting status to failed with message."""
        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        log.set_status(DispatchStatus.FAILED, "Connection refused")
        log.refresh_from_db()

        assert log.status == DispatchStatus.FAILED
        assert log.status_message == "Connection refused"

    def test_duration_ms(self, organization, output_route):
        """Test duration calculation."""
        from django.utils import timezone
        from datetime import timedelta

        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        # No duration when not sent
        assert log.duration_ms is None

        # Set timing
        log.sent_at = timezone.now()
        log.completed_at = log.sent_at + timedelta(milliseconds=250)
        log.save()

        assert log.duration_ms == 250

    def test_string_representation(self, organization, output_route):
        """Test string representation."""
        log = DispatchLog.objects.create(
            organization=organization,
            route=output_route,
            destination_type=DestinationType.WEBHOOK,
        )

        str_repr = str(log)
        assert "webhook" in str_repr.lower()
        assert "pending" in str_repr.lower()


class TestDestinationType:
    """Tests for DestinationType enum."""

    def test_destination_types(self):
        """Test all destination types are defined."""
        assert DestinationType.SLACK == "slack"
        assert DestinationType.DISCORD == "discord"
        assert DestinationType.WEBHOOK == "webhook"
        assert DestinationType.DOCUMENT == "document"
        assert DestinationType.EMAIL == "email"
        assert DestinationType.PLATFORM_REPLY == "platform_reply"


class TestDispatchStatus:
    """Tests for DispatchStatus enum."""

    def test_dispatch_statuses(self):
        """Test all dispatch statuses are defined."""
        assert DispatchStatus.PENDING == "pending"
        assert DispatchStatus.SENDING == "sending"
        assert DispatchStatus.SUCCESS == "success"
        assert DispatchStatus.FAILED == "failed"
        assert DispatchStatus.SKIPPED == "skipped"
