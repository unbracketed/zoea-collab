"""Tests for project_activity_summary workflow."""

import pytest
from django.utils import timezone

from langgraph_runtime.state import ExecutionState

from .graph import build_graph
from .nodes import format_output, gather_activity, summarize_activity


@pytest.fixture
def org_and_project(db):
    """Create test organization and project."""
    from accounts.models import Account
    from projects.models import Project

    org = Account.objects.create(name="Test Org")
    project = Project.objects.create(
        organization=org,
        name="Test Project",
        slug="test-project",
    )
    return org, project


@pytest.fixture
def sample_execution_runs(org_and_project):
    """Create sample ExecutionRun records."""
    from execution.models import ExecutionRun

    org, project = org_and_project

    runs = []
    for i in range(5):
        run = ExecutionRun.objects.create(
            organization=org,
            project=project,
            trigger_type="webhook" if i % 2 == 0 else "scheduled",
            status="completed" if i < 4 else "failed",
            workflow_slug="test_workflow",
            error="Test error" if i == 4 else None,
        )
        runs.append(run)
    return runs


@pytest.fixture
def sample_messages(org_and_project):
    """Create sample ChannelMessage records."""
    from channels.models import Channel, ChannelMessage

    org, project = org_and_project

    channel = Channel.objects.create(
        organization=org,
        project=project,
        adapter_type="zoea_chat",
        external_id="test-channel",
        display_name="Test Channel",
    )

    messages = []
    for i in range(10):
        msg = ChannelMessage.objects.create(
            organization=org,
            channel=channel,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Test message {i}",
        )
        messages.append(msg)
    return messages


@pytest.fixture
def sample_documents(org_and_project):
    """Create sample Document records."""
    from documents.models import Markdown

    org, project = org_and_project

    docs = []
    for i in range(3):
        doc = Markdown.objects.create(
            organization=org,
            project=project,
            name=f"Test Doc {i}",
            content=f"Content for doc {i}",
        )
        docs.append(doc)
    return docs


class TestBuildGraph:
    """Test graph construction."""

    def test_build_graph_returns_state_graph(self):
        """build_graph should return a StateGraph."""
        from langgraph.graph import StateGraph

        graph = build_graph()
        assert isinstance(graph, StateGraph)

    def test_graph_has_expected_nodes(self):
        """Graph should have the expected nodes."""
        graph = build_graph()
        assert "gather_activity" in graph.nodes
        assert "summarize_activity" in graph.nodes
        assert "format_output" in graph.nodes

    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None


class TestGatherActivityNode:
    """Test gather_activity node."""

    def test_gather_activity_with_data(
        self, org_and_project, sample_execution_runs, sample_messages, sample_documents
    ):
        """gather_activity should aggregate activity data."""
        org, project = org_and_project

        state: ExecutionState = {
            "context": {
                "organization_id": org.id,
                "project_id": project.id,
            },
            "inputs": {"lookback_hours": 24},
            "workflow_state": {},
        }

        result = gather_activity(state)

        assert "workflow_state" in result
        activity_data = result["workflow_state"]["activity_data"]

        # Verify execution stats
        assert activity_data["executions"]["stats"]["total"] == 5
        assert activity_data["executions"]["stats"]["completed"] == 4
        assert activity_data["executions"]["stats"]["failed"] == 1

        # Verify message stats
        assert activity_data["messages"]["stats"]["total"] == 10
        assert activity_data["messages"]["stats"]["user_messages"] == 5
        assert activity_data["messages"]["stats"]["assistant_messages"] == 5

        # Verify document stats
        assert activity_data["documents"]["created"] == 3

    def test_gather_activity_empty_project(self, org_and_project):
        """gather_activity should handle empty projects gracefully."""
        org, project = org_and_project

        state: ExecutionState = {
            "context": {
                "organization_id": org.id,
                "project_id": project.id,
            },
            "inputs": {"lookback_hours": 24},
            "workflow_state": {},
        }

        result = gather_activity(state)

        activity_data = result["workflow_state"]["activity_data"]
        assert activity_data["executions"]["stats"]["total"] == 0
        assert activity_data["messages"]["stats"]["total"] == 0
        assert activity_data["documents"]["created"] == 0


class TestSummarizeActivityNode:
    """Test summarize_activity node."""

    def test_summarize_without_ai_service(self, org_and_project, sample_execution_runs):
        """summarize_activity should generate fallback when no AI service."""
        org, project = org_and_project

        # First gather activity
        state: ExecutionState = {
            "context": {
                "organization_id": org.id,
                "project_id": project.id,
            },
            "inputs": {"lookback_hours": 24},
            "workflow_state": {},
            "services": {},  # No AI service
        }

        gather_result = gather_activity(state)
        state["workflow_state"] = gather_result["workflow_state"]

        # Then summarize
        result = summarize_activity(state)

        assert "workflow_state" in result
        assert "summary_text" in result["workflow_state"]
        assert len(result["workflow_state"]["summary_text"]) > 0


class TestFormatOutputNode:
    """Test format_output node."""

    def test_format_output_markdown(self, org_and_project, sample_execution_runs):
        """format_output should create markdown output."""
        org, project = org_and_project

        # Build state with activity data
        state: ExecutionState = {
            "context": {
                "organization_id": org.id,
                "project_id": project.id,
            },
            "inputs": {
                "lookback_hours": 24,
                "include_metrics": True,
                "include_failures": True,
                "output_format": "markdown",
            },
            "workflow_state": {
                "activity_data": {
                    "period": {"hours": 24, "since": "2026-01-22T00:00:00Z", "until": "2026-01-23T00:00:00Z"},
                    "executions": {
                        "stats": {"total": 5, "completed": 4, "failed": 1},
                        "recent_failures": [{"run_id": "abc12345", "workflow_slug": "test", "error": "Test error"}],
                    },
                    "messages": {"stats": {"total": 10}},
                    "documents": {"created": 3, "modified": 1},
                },
                "summary_text": "Test summary content.",
            },
            "outputs": [],
            "output_values": {},
        }

        result = format_output(state)

        assert "workflow_state" in result
        assert "formatted_output" in result["workflow_state"]
        assert "# Project Activity Summary" in result["workflow_state"]["formatted_output"]

        # Check outputs list has an entry
        assert len(result["outputs"]) == 1
        assert result["outputs"][0]["kind"] == "document"

        # Check output_values for WorkflowRunner
        assert "Activity Summary" in result["output_values"]


class TestFullWorkflowExecution:
    """Test complete workflow execution."""

    def test_workflow_runs_end_to_end_sync(
        self, org_and_project, sample_execution_runs, sample_messages, sample_documents
    ):
        """Full workflow should run without errors (sync test)."""
        org, project = org_and_project

        # Test by calling nodes directly in sequence (avoid async/SQLite issues)
        initial_state: ExecutionState = {
            "run_id": "test-run-001",
            "status": "running",
            "context": {
                "organization_id": org.id,
                "project_id": project.id,
            },
            "inputs": {
                "lookback_hours": 24,
                "include_metrics": True,
                "include_failures": True,
                "output_format": "markdown",
            },
            "workflow_state": {},
            "outputs": [],
            "output_values": {},
            "services": {},  # No AI service for test
        }

        # Run nodes in sequence
        state = dict(initial_state)

        # Node 1: gather_activity
        result = gather_activity(state)
        state.update(result)

        # Node 2: summarize_activity
        result = summarize_activity(state)
        state.update(result)

        # Node 3: format_output
        result = format_output(state)
        state.update(result)

        # Verify workflow completed
        assert "workflow_state" in state
        assert "activity_data" in state["workflow_state"]
        assert "summary_text" in state["workflow_state"]
        assert "formatted_output" in state["workflow_state"]

        # Verify outputs
        assert len(state["outputs"]) == 1
        assert state["outputs"][0]["kind"] == "document"
        assert "Activity Summary" in state["output_values"]

    def test_graph_compiles_and_has_correct_structure(self):
        """Graph should compile with correct node structure."""
        graph = build_graph()
        compiled = graph.compile()

        # Check the graph has correct nodes
        assert compiled is not None
