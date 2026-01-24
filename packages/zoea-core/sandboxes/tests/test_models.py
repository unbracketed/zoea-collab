"""Tests for sandboxes models."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from projects.models import Project
from sandboxes.models import (
    SandboxConfig,
    SandboxSession,
    SandboxType,
    SessionStatus,
)

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
def sandbox_config(db, organization, user):
    """Create a test sandbox config."""
    return SandboxConfig.objects.create(
        organization=organization,
        name="Test Tmux Config",
        description="Test configuration for tmux sandbox",
        sandbox_type=SandboxType.TMUX,
        is_default=True,
        resource_limits={
            "timeout_seconds": 300,
            "max_output_size": 1048576,
        },
        environment_variables={
            "TEST_VAR": "test_value",
        },
        created_by=user,
    )


class TestSandboxConfig:
    """Tests for SandboxConfig model."""

    def test_create_config(self, organization, user):
        """Test creating a sandbox config."""
        config = SandboxConfig.objects.create(
            organization=organization,
            name="Test Config",
            sandbox_type=SandboxType.TMUX,
            created_by=user,
        )

        assert config.id is not None
        assert config.name == "Test Config"
        assert config.sandbox_type == SandboxType.TMUX
        assert config.is_default is False
        assert config.network_enabled is True
        assert config.shell_command == "/bin/bash"

    def test_create_docker_config(self, organization, user):
        """Test creating a Docker sandbox config."""
        config = SandboxConfig.objects.create(
            organization=organization,
            name="Docker Config",
            sandbox_type=SandboxType.DOCKER,
            docker_image="python:3.12-slim",
            network_enabled=False,
            created_by=user,
        )

        assert config.sandbox_type == SandboxType.DOCKER
        assert config.docker_image == "python:3.12-slim"
        assert config.network_enabled is False

    def test_get_resource_limit(self, sandbox_config):
        """Test getting resource limits."""
        assert sandbox_config.get_resource_limit("timeout_seconds") == 300
        assert sandbox_config.get_resource_limit("nonexistent", "default") == "default"

    def test_get_timeout_seconds(self, sandbox_config):
        """Test getting timeout."""
        assert sandbox_config.get_timeout_seconds() == 300

    def test_get_timeout_seconds_default(self, organization, user):
        """Test default timeout when not configured."""
        config = SandboxConfig.objects.create(
            organization=organization,
            name="No Limits Config",
            sandbox_type=SandboxType.TMUX,
            created_by=user,
        )

        assert config.get_timeout_seconds() == 600  # Default 10 minutes

    def test_string_representation(self, sandbox_config):
        """Test string representation."""
        expected = "Test Tmux Config (Tmux Session)"
        assert str(sandbox_config) == expected


class TestSandboxSession:
    """Tests for SandboxSession model."""

    def test_create_session(self, organization, sandbox_config, user):
        """Test creating a sandbox session."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            name="Test Session",
            created_by=user,
        )

        assert session.id is not None
        assert session.session_id is not None
        assert session.status == SessionStatus.PENDING
        assert session.execution_count == 0
        assert session.sandbox_type == SandboxType.TMUX

    def test_create_session_with_project(self, organization, project, sandbox_config, user):
        """Test creating a session scoped to a project."""
        session = SandboxSession.objects.create(
            organization=organization,
            project=project,
            config=sandbox_config,
            name="Project Session",
            created_by=user,
        )

        assert session.project == project

    def test_set_status_ready(self, organization, sandbox_config, user):
        """Test setting status to ready updates started_at."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            created_by=user,
        )

        assert session.started_at is None

        session.set_status(SessionStatus.READY)
        session.refresh_from_db()

        assert session.status == SessionStatus.READY
        assert session.started_at is not None

    def test_set_status_terminated(self, organization, sandbox_config, user):
        """Test setting status to terminated updates terminated_at."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            created_by=user,
        )

        session.set_status(SessionStatus.TERMINATED)
        session.refresh_from_db()

        assert session.status == SessionStatus.TERMINATED
        assert session.terminated_at is not None

    def test_record_activity(self, organization, sandbox_config, user):
        """Test recording activity updates counters."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            created_by=user,
        )

        assert session.execution_count == 0
        assert session.last_activity_at is None

        session.record_activity()
        session.refresh_from_db()

        assert session.execution_count == 1
        assert session.last_activity_at is not None

    def test_duration_seconds(self, organization, sandbox_config, user):
        """Test duration calculation."""
        from django.utils import timezone
        from datetime import timedelta

        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            created_by=user,
        )

        # No duration when not started
        assert session.duration_seconds is None

        # Set timing
        session.started_at = timezone.now()
        session.terminated_at = session.started_at + timedelta(seconds=10.5)
        session.save()

        assert session.duration_seconds == pytest.approx(10.5, rel=0.1)

    def test_get_runtime_identifier_tmux(self, organization, sandbox_config, user):
        """Test getting runtime identifier for tmux session."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            tmux_session_name="test_session",
            created_by=user,
        )

        assert session.get_runtime_identifier() == "test_session"

    def test_get_runtime_identifier_docker(self, organization, user):
        """Test getting runtime identifier for docker session."""
        config = SandboxConfig.objects.create(
            organization=organization,
            name="Docker Config",
            sandbox_type=SandboxType.DOCKER,
        )

        session = SandboxSession.objects.create(
            organization=organization,
            config=config,
            container_id="abc123",
            created_by=user,
        )

        assert session.get_runtime_identifier() == "abc123"

    def test_string_representation(self, organization, sandbox_config, user):
        """Test string representation."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=sandbox_config,
            name="Named Session",
            created_by=user,
        )

        assert "Named Session" in str(session)
        assert "pending" in str(session).lower()

    def test_sandbox_type_from_runtime_config(self, organization, user):
        """Test getting sandbox type from runtime config when no config."""
        session = SandboxSession.objects.create(
            organization=organization,
            config=None,
            runtime_config={"sandbox_type": SandboxType.DOCKER},
            created_by=user,
        )

        assert session.sandbox_type == SandboxType.DOCKER


class TestSandboxType:
    """Tests for SandboxType enum."""

    def test_sandbox_types(self):
        """Test all sandbox types are defined."""
        assert SandboxType.TMUX == "tmux"
        assert SandboxType.DOCKER == "docker"
        assert SandboxType.VM == "vm"


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_session_statuses(self):
        """Test all session statuses are defined."""
        assert SessionStatus.PENDING == "pending"
        assert SessionStatus.CREATING == "creating"
        assert SessionStatus.READY == "ready"
        assert SessionStatus.RUNNING == "running"
        assert SessionStatus.ERROR == "error"
        assert SessionStatus.TERMINATED == "terminated"
