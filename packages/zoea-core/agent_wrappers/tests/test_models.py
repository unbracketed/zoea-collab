"""Tests for agent_wrappers models."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import Account
from agent_wrappers.models import (
    AgentRunStatus,
    AgentType,
    ExternalAgentConfig,
    ExternalAgentRun,
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
def agent_config(db, organization, user):
    """Create a test agent config."""
    return ExternalAgentConfig.objects.create(
        organization=organization,
        name="Test Claude Code",
        description="Test Claude Code configuration",
        agent_type=AgentType.CLAUDE_CODE,
        is_default=True,
        settings={
            "output_format": "text",
            "model": "claude-3-opus",
        },
        max_steps=100,
        timeout_seconds=300,
        created_by=user,
    )


class TestExternalAgentConfig:
    """Tests for ExternalAgentConfig model."""

    def test_create_config(self, organization, user):
        """Test creating an agent config."""
        config = ExternalAgentConfig.objects.create(
            organization=organization,
            name="Test Config",
            agent_type=AgentType.CLAUDE_CODE,
            created_by=user,
        )

        assert config.id is not None
        assert config.name == "Test Config"
        assert config.agent_type == AgentType.CLAUDE_CODE
        assert config.is_enabled is True
        assert config.is_default is False
        assert config.max_steps == 50
        assert config.timeout_seconds == 600

    def test_create_codex_config(self, organization, user):
        """Test creating a Codex config."""
        config = ExternalAgentConfig.objects.create(
            organization=organization,
            name="Codex Config",
            agent_type=AgentType.CODEX,
            credentials={"api_key": "test-key"},
            created_by=user,
        )

        assert config.agent_type == AgentType.CODEX
        assert config.credentials == {"api_key": "test-key"}

    def test_get_credential(self, agent_config):
        """Test getting credentials."""
        # No credentials set
        assert agent_config.get_credential("api_key") is None
        assert agent_config.get_credential("api_key", "default") == "default"

    def test_get_setting(self, agent_config):
        """Test getting settings."""
        assert agent_config.get_setting("output_format") == "text"
        assert agent_config.get_setting("model") == "claude-3-opus"
        assert agent_config.get_setting("nonexistent") is None
        assert agent_config.get_setting("nonexistent", "default") == "default"

    def test_get_cli_command_default(self, organization, user):
        """Test default CLI command."""
        config = ExternalAgentConfig.objects.create(
            organization=organization,
            name="Claude Config",
            agent_type=AgentType.CLAUDE_CODE,
            created_by=user,
        )

        assert config.get_cli_command() == "claude"

    def test_get_cli_command_custom(self, organization, user):
        """Test custom CLI command."""
        config = ExternalAgentConfig.objects.create(
            organization=organization,
            name="Custom Config",
            agent_type=AgentType.CUSTOM,
            cli_command="/usr/local/bin/my-agent",
            created_by=user,
        )

        assert config.get_cli_command() == "/usr/local/bin/my-agent"

    def test_string_representation(self, agent_config):
        """Test string representation."""
        expected = "Test Claude Code (Claude Code)"
        assert str(agent_config) == expected


class TestExternalAgentRun:
    """Tests for ExternalAgentRun model."""

    def test_create_run(self, organization, agent_config, user):
        """Test creating an agent run."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Write a hello world function",
            created_by=user,
        )

        assert run.id is not None
        assert run.run_id is not None
        assert run.status == AgentRunStatus.PENDING
        assert run.steps_taken == 0
        assert run.agent_type == AgentType.CLAUDE_CODE

    def test_create_run_with_project(self, organization, project, agent_config, user):
        """Test creating a run scoped to a project."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            project=project,
            config=agent_config,
            prompt="Test prompt",
            created_by=user,
        )

        assert run.project == project

    def test_set_status_running(self, organization, agent_config, user):
        """Test setting status to running updates started_at."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        assert run.started_at is None

        run.set_status(AgentRunStatus.RUNNING)
        run.refresh_from_db()

        assert run.status == AgentRunStatus.RUNNING
        assert run.started_at is not None

    def test_set_status_completed(self, organization, agent_config, user):
        """Test setting status to completed updates completed_at."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        run.set_status(AgentRunStatus.COMPLETED)
        run.refresh_from_db()

        assert run.status == AgentRunStatus.COMPLETED
        assert run.completed_at is not None

    def test_set_status_failed(self, organization, agent_config, user):
        """Test setting status to failed with message."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        run.set_status(AgentRunStatus.FAILED, "Something went wrong")
        run.refresh_from_db()

        assert run.status == AgentRunStatus.FAILED
        assert run.status_message == "Something went wrong"

    def test_duration_seconds(self, organization, agent_config, user):
        """Test duration calculation."""
        from django.utils import timezone
        from datetime import timedelta

        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        # No duration when not started
        assert run.duration_seconds is None

        # Set timing
        run.started_at = timezone.now()
        run.completed_at = run.started_at + timedelta(seconds=15.5)
        run.save()

        assert run.duration_seconds == pytest.approx(15.5, rel=0.1)

    def test_add_artifact(self, organization, agent_config, user):
        """Test adding artifacts."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        assert run.artifacts == []

        run.add_artifact({"path": "test.py", "action": "created"})
        run.refresh_from_db()

        assert len(run.artifacts) == 1
        assert run.artifacts[0]["path"] == "test.py"

        run.add_artifact({"path": "utils.py", "action": "modified"})
        run.refresh_from_db()

        assert len(run.artifacts) == 2

    def test_update_tokens(self, organization, agent_config, user):
        """Test updating token usage."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        assert run.tokens_used == {}

        run.update_tokens(prompt_tokens=100, completion_tokens=50)
        run.refresh_from_db()

        assert run.tokens_used["prompt_tokens"] == 100
        assert run.tokens_used["completion_tokens"] == 50
        assert run.tokens_used["total_tokens"] == 150

        # Accumulate tokens
        run.update_tokens(prompt_tokens=50, completion_tokens=25)
        run.refresh_from_db()

        assert run.tokens_used["prompt_tokens"] == 150
        assert run.tokens_used["completion_tokens"] == 75
        assert run.tokens_used["total_tokens"] == 225

    def test_agent_type_from_runtime_config(self, organization, user):
        """Test getting agent type from runtime config when no config."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=None,
            prompt="Test",
            runtime_config={"agent_type": AgentType.CODEX},
            created_by=user,
        )

        assert run.agent_type == AgentType.CODEX

    def test_string_representation(self, organization, agent_config, user):
        """Test string representation."""
        run = ExternalAgentRun.objects.create(
            organization=organization,
            config=agent_config,
            prompt="Test",
            created_by=user,
        )

        str_repr = str(run)
        assert "Test Claude Code" in str_repr
        assert "pending" in str_repr.lower()


class TestAgentType:
    """Tests for AgentType enum."""

    def test_agent_types(self):
        """Test all agent types are defined."""
        assert AgentType.CLAUDE_CODE == "claude_code"
        assert AgentType.CODEX == "codex"
        assert AgentType.OPENCODE == "opencode"
        assert AgentType.SHELLEY == "shelley"
        assert AgentType.CUSTOM == "custom"


class TestAgentRunStatus:
    """Tests for AgentRunStatus enum."""

    def test_run_statuses(self):
        """Test all run statuses are defined."""
        assert AgentRunStatus.PENDING == "pending"
        assert AgentRunStatus.RUNNING == "running"
        assert AgentRunStatus.COMPLETED == "completed"
        assert AgentRunStatus.FAILED == "failed"
        assert AgentRunStatus.CANCELLED == "cancelled"
        assert AgentRunStatus.TIMEOUT == "timeout"
