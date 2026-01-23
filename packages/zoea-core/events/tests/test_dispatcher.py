"""
Tests for event dispatcher.
"""

import pytest
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model

from accounts.models import Account
from events.dispatcher import EventDispatcher, dispatch_event
from events.models import EventTrigger, EventType
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


@pytest.fixture
def email_trigger(organization, user):
    """Create an email trigger."""
    return EventTrigger.objects.create(
        organization=organization,
        name="Email Handler",
        event_type=EventType.EMAIL_RECEIVED,
        skills=["extract-data"],
        is_enabled=True,
        run_async=False,  # Sync for testing
        created_by=user,
    )


@pytest.mark.django_db
class TestEventDispatcher:
    """Tests for EventDispatcher."""

    def test_no_matching_triggers(self, organization):
        """Test dispatch when no triggers match."""
        dispatcher = EventDispatcher()

        runs = dispatcher.dispatch(
            event_type=EventType.EMAIL_RECEIVED,
            source_type="email_message",
            source_id=1,
            event_data={"subject": "Test"},
            organization=organization,
        )

        assert runs == []

    def test_find_matching_trigger(self, organization, email_trigger):
        """Test finding a matching trigger."""
        dispatcher = EventDispatcher()

        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.EMAIL_RECEIVED.value,
            organization=organization,
            project=None,
            event_data={},
        )

        assert len(triggers) == 1
        assert triggers[0] == email_trigger

    def test_disabled_trigger_not_matched(self, organization, email_trigger):
        """Test that disabled triggers are not matched."""
        email_trigger.is_enabled = False
        email_trigger.save()

        dispatcher = EventDispatcher()

        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.EMAIL_RECEIVED.value,
            organization=organization,
            project=None,
            event_data={},
        )

        assert len(triggers) == 0

    def test_project_scoped_trigger(self, organization, project, user):
        """Test project-scoped triggers only match their project."""
        # Create project-scoped trigger
        trigger = EventTrigger.objects.create(
            organization=organization,
            project=project,
            name="Project Trigger",
            event_type=EventType.DOCUMENT_CREATED,
            skills=["test"],
            created_by=user,
        )

        dispatcher = EventDispatcher()

        # Should match with project
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=project,
            event_data={},
        )
        assert len(triggers) == 1

        # Should not match without project
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=None,
            event_data={},
        )
        assert len(triggers) == 0

    def test_filter_matching(self, organization, user):
        """Test filter matching logic."""
        # Create trigger with filter
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="Filtered Trigger",
            event_type=EventType.DOCUMENT_CREATED,
            skills=["test"],
            filters={"document_type": "MarkdownDocument"},
            created_by=user,
        )

        dispatcher = EventDispatcher()

        # Should match with correct document type
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=None,
            event_data={"document_type": "MarkdownDocument"},
        )
        assert len(triggers) == 1

        # Should not match with different document type
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=None,
            event_data={"document_type": "ImageDocument"},
        )
        assert len(triggers) == 0

    def test_list_filter_matching(self, organization, user):
        """Test filter matching with list values."""
        trigger = EventTrigger.objects.create(
            organization=organization,
            name="List Filtered Trigger",
            event_type=EventType.DOCUMENT_CREATED,
            skills=["test"],
            filters={"document_type": ["MarkdownDocument", "TextDocument"]},
            created_by=user,
        )

        dispatcher = EventDispatcher()

        # Should match with value in list
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=None,
            event_data={"document_type": "MarkdownDocument"},
        )
        assert len(triggers) == 1

        # Should not match with value not in list
        triggers = dispatcher._find_matching_triggers(
            event_type=EventType.DOCUMENT_CREATED.value,
            organization=organization,
            project=None,
            event_data={"document_type": "ImageDocument"},
        )
        assert len(triggers) == 0

    @patch("events.dispatcher.EventDispatcher._execute_sync")
    def test_dispatch_creates_run(self, mock_execute, organization, email_trigger):
        """Test that dispatch creates ExecutionRun records."""
        dispatcher = EventDispatcher()

        runs = dispatcher.dispatch(
            event_type=EventType.EMAIL_RECEIVED,
            source_type="email_message",
            source_id=123,
            event_data={"subject": "Test Email", "body": "Hello"},
            organization=organization,
        )

        assert len(runs) == 1
        run = runs[0]

        assert run.trigger == email_trigger
        assert run.source_type == "email_message"
        assert run.source_id == 123
        assert run.inputs == {"subject": "Test Email", "body": "Hello"}
        assert run.status == ExecutionRun.Status.PENDING

        # Verify sync execution was called
        mock_execute.assert_called_once()


@pytest.mark.django_db
class TestDispatchEventFunction:
    """Tests for dispatch_event convenience function."""

    @patch("events.dispatcher.EventDispatcher._execute_sync")
    def test_dispatch_event(self, mock_execute, organization, email_trigger):
        """Test the dispatch_event convenience function."""
        runs = dispatch_event(
            event_type=EventType.EMAIL_RECEIVED,
            source_type="email_message",
            source_id=1,
            event_data={"test": "data"},
            organization=organization,
        )

        assert len(runs) == 1
