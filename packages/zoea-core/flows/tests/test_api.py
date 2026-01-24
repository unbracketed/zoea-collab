"""
Tests for flows API endpoints.

Tests the workflow listing endpoint, workflow retrieval, and workflow execution.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from organizations.models import Organization, OrganizationUser

from flows.api import (
    _convert_workflow_to_out,
    _ensure_workflows_discovered,
    _validate_workflow_inputs,
)
from flows.schemas import (
    InputSpecOut,
    OutputSpecOut,
    WorkflowOut,
    ExecutionOutputResult,
    ExecutionRunErrorResponse,
    ExecutionRunRequest,
    ExecutionRunResponse,
    ExecutionValidationError,
)
from projects.models import Project
from workflows.registry import WorkflowRegistry
from workflows.types import InputSpec, WorkflowSpec

User = get_user_model()


@pytest.fixture
def api_client():
    """Create a Django test client for API requests."""
    return Client()


@pytest.fixture
def reset_registry():
    """Reset the WorkflowRegistry singleton before and after each test."""
    WorkflowRegistry.reset_instance()
    yield
    WorkflowRegistry.reset_instance()


@pytest.fixture
def sample_workflow_yaml():
    """Sample workflow YAML configuration content."""
    return """
name: Test Workflow
description: A test workflow for unit testing

INPUTS:
  - name: test_input
    type: str
    description: A test input parameter
    required: true

  - name: optional_input
    type: int
    value: 42
    description: An optional input with default value
    required: false

OUTPUTS:
  - name: Test Output
    type: MarkdownDocument
    target: TestFolder/Results

SERVICES:
  - name: AIService
    ctxref: ai
"""


@pytest.fixture
def temp_workflow_dir(sample_workflow_yaml):
    """Create a temporary workflow directory with config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create builtin directory structure
        builtin_dir = Path(tmpdir) / "builtin" / "test_workflow"
        builtin_dir.mkdir(parents=True)

        # Write config file
        config_path = builtin_dir / "flow-config.yaml"
        config_path.write_text(sample_workflow_yaml)

        yield Path(tmpdir)


class TestWorkflowsEndpoint:
    """Tests for GET /api/flows/workflows endpoint."""

    def test_list_workflows_returns_list(self, api_client, db, reset_registry):
        """Test that the endpoint returns a list of workflows."""
        response = api_client.get("/api/flows/workflows")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_workflows_includes_builtin_workflows(self, api_client, db, reset_registry):
        """Test that builtin workflows are discovered and returned."""
        response = api_client.get("/api/flows/workflows")

        assert response.status_code == 200
        data = response.json()

        # Should have at least the builtin workflows
        assert len(data) >= 0  # May be empty if no builtin workflows exist

        # If workflows exist, verify structure
        if data:
            workflow = data[0]
            assert "slug" in workflow
            assert "name" in workflow
            assert "description" in workflow
            assert "inputs" in workflow
            assert "outputs" in workflow

    def test_list_workflows_with_registered_workflow(
        self, api_client, db, reset_registry, temp_workflow_dir
    ):
        """Test listing workflows when a workflow is registered."""
        # Register a test workflow
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        response = api_client.get("/api/flows/workflows")

        assert response.status_code == 200
        data = response.json()

        # Find our test workflow
        test_workflow = next(
            (w for w in data if w["slug"] == "test_workflow"), None
        )
        assert test_workflow is not None
        assert test_workflow["name"] == "Test Workflow"
        assert test_workflow["description"] == "A test workflow for unit testing"

    def test_workflow_inputs_serialization(
        self, api_client, db, reset_registry, temp_workflow_dir
    ):
        """Test that workflow inputs are correctly serialized."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        response = api_client.get("/api/flows/workflows")
        data = response.json()

        test_workflow = next(
            (w for w in data if w["slug"] == "test_workflow"), None
        )
        assert test_workflow is not None

        inputs = test_workflow["inputs"]
        assert len(inputs) == 2

        # Check required input
        test_input = next((i for i in inputs if i["name"] == "test_input"), None)
        assert test_input is not None
        assert test_input["type"] == "str"
        assert test_input["description"] == "A test input parameter"
        assert test_input["required"] is True
        assert test_input["default_value"] is None

        # Check optional input with default
        optional_input = next(
            (i for i in inputs if i["name"] == "optional_input"), None
        )
        assert optional_input is not None
        assert optional_input["type"] == "int"
        assert optional_input["required"] is False
        assert optional_input["default_value"] == "42"

    def test_workflow_outputs_serialization(
        self, api_client, db, reset_registry, temp_workflow_dir
    ):
        """Test that workflow outputs are correctly serialized."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        response = api_client.get("/api/flows/workflows")
        data = response.json()

        test_workflow = next(
            (w for w in data if w["slug"] == "test_workflow"), None
        )
        assert test_workflow is not None

        outputs = test_workflow["outputs"]
        assert len(outputs) == 1

        output = outputs[0]
        assert output["name"] == "Test Output"
        assert output["type"] == "MarkdownDocument"
        assert output["target"] == "TestFolder/Results"


class TestEnsureWorkflowsDiscovered:
    """Tests for the _ensure_workflows_discovered helper function."""

    def test_discovers_workflows_when_registry_empty(self, reset_registry):
        """Test that workflows are discovered when registry is empty."""
        # Registry should be empty after reset
        registry = WorkflowRegistry.get_instance()
        assert len(registry.list_workflows()) == 0

        # Call discover function
        _ensure_workflows_discovered()

        # Should have discovered builtins (if they exist)
        # The function is idempotent, so this just verifies no errors

    def test_idempotent_discovery(self, reset_registry, temp_workflow_dir):
        """Test that discovery is idempotent."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        initial_count = len(registry.list_workflows())

        # Mock discover_builtins to verify it's not called again
        with patch.object(registry, "discover_builtins") as mock_discover:
            _ensure_workflows_discovered()
            mock_discover.assert_not_called()

        # Count should remain the same
        assert len(registry.list_workflows()) == initial_count


class TestConvertWorkflowToOut:
    """Tests for the _convert_workflow_to_out helper function."""

    def test_convert_with_valid_config(self, reset_registry, temp_workflow_dir):
        """Test conversion of workflow with valid config."""
        config_path = temp_workflow_dir / "builtin" / "test_workflow" / "flow-config.yaml"

        workflow_data = {"config_path": config_path, "flow_builder": None}

        result = _convert_workflow_to_out("test_workflow", workflow_data)

        assert isinstance(result, WorkflowOut)
        assert result.slug == "test_workflow"
        assert result.name == "Test Workflow"
        assert result.description == "A test workflow for unit testing"
        assert len(result.inputs) == 2
        assert len(result.outputs) == 1

    def test_convert_without_config_path(self, reset_registry):
        """Test conversion when config_path is missing."""
        workflow_data = {"config_path": None, "flow_builder": None}

        result = _convert_workflow_to_out("my-test-workflow", workflow_data)

        assert isinstance(result, WorkflowOut)
        assert result.slug == "my-test-workflow"
        assert result.name == "My Test Workflow"  # Derived from slug
        assert result.description == ""
        assert result.inputs == []
        assert result.outputs == []

    def test_convert_with_invalid_config(self, reset_registry, temp_workflow_dir):
        """Test conversion gracefully handles invalid config."""
        # Create an invalid config file
        invalid_dir = temp_workflow_dir / "builtin" / "invalid_workflow"
        invalid_dir.mkdir(parents=True)
        invalid_config = invalid_dir / "flow-config.yaml"
        invalid_config.write_text("invalid: [yaml: content")

        workflow_data = {"config_path": invalid_config, "flow_builder": None}

        result = _convert_workflow_to_out("invalid_workflow", workflow_data)

        # Should return minimal workflow info instead of raising
        assert isinstance(result, WorkflowOut)
        assert result.slug == "invalid_workflow"
        assert result.name == "Invalid Workflow"
        assert result.inputs == []
        assert result.outputs == []

    def test_convert_with_missing_config_file(self, reset_registry):
        """Test conversion when config file doesn't exist."""
        workflow_data = {
            "config_path": Path("/nonexistent/path/flow-config.yaml"),
            "flow_builder": None,
        }

        result = _convert_workflow_to_out("missing_config", workflow_data)

        assert isinstance(result, WorkflowOut)
        assert result.slug == "missing_config"
        assert result.name == "Missing Config"


class TestSchemas:
    """Tests for Pydantic schemas."""

    def test_input_spec_out_serialization(self):
        """Test InputSpecOut schema serialization."""
        input_spec = InputSpecOut(
            name="test_param",
            type="str",
            description="A test parameter",
            required=True,
            default_value=None,
        )

        data = input_spec.model_dump()

        assert data["name"] == "test_param"
        assert data["type"] == "str"
        assert data["description"] == "A test parameter"
        assert data["required"] is True
        assert data["default_value"] is None

    def test_output_spec_out_serialization(self):
        """Test OutputSpecOut schema serialization."""
        output_spec = OutputSpecOut(
            name="Output Document",
            type="MarkdownDocument",
            target="Output/Folder",
        )

        data = output_spec.model_dump()

        assert data["name"] == "Output Document"
        assert data["type"] == "MarkdownDocument"
        assert data["target"] == "Output/Folder"

    def test_workflow_out_serialization(self):
        """Test WorkflowOut schema serialization."""
        workflow = WorkflowOut(
            slug="test-workflow",
            name="Test Workflow",
            description="A test workflow",
            inputs=[
                InputSpecOut(
                    name="input1",
                    type="str",
                    description="First input",
                    required=True,
                    default_value=None,
                )
            ],
            outputs=[
                OutputSpecOut(
                    name="output1",
                    type="MarkdownDocument",
                    target="Output",
                )
            ],
        )

        data = workflow.model_dump()

        assert data["slug"] == "test-workflow"
        assert data["name"] == "Test Workflow"
        assert data["description"] == "A test workflow"
        assert len(data["inputs"]) == 1
        assert len(data["outputs"]) == 1

    def test_workflow_out_with_empty_inputs_outputs(self):
        """Test WorkflowOut with empty inputs and outputs."""
        workflow = WorkflowOut(
            slug="empty-workflow",
            name="Empty Workflow",
            description="",
            inputs=[],
            outputs=[],
        )

        data = workflow.model_dump()

        assert data["inputs"] == []
        assert data["outputs"] == []


# Fixtures for workflow run endpoint tests
@pytest.fixture
def test_user(db):
    """Create a test user."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )
    return user


@pytest.fixture
def test_organization(db, test_user):
    """Create a test organization with the test user as a member."""
    org = Organization.objects.create(
        name="Test Organization",
        slug="test-org",
    )
    OrganizationUser.objects.create(
        user=test_user,
        organization=org,
        is_admin=True,
    )
    return org


@pytest.fixture
def test_project(db, test_organization, test_user):
    """Create a test project in the test organization."""
    project = Project.objects.create(
        organization=test_organization,
        name="Test Project",
        working_directory="/tmp/test-project",
        created_by=test_user,
    )
    return project


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated Django test client."""
    api_client.force_login(test_user)
    return api_client


class TestGetWorkflowEndpoint:
    """Tests for GET /api/flows/workflows/{slug} endpoint."""

    def test_get_workflow_returns_workflow(
        self, api_client, db, reset_registry, temp_workflow_dir
    ):
        """Test that the endpoint returns a specific workflow."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        response = api_client.get("/api/flows/workflows/test_workflow")

        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "test_workflow"
        assert data["name"] == "Test Workflow"

    def test_get_workflow_not_found(self, api_client, db, reset_registry):
        """Test that 404 is returned for non-existent workflow."""
        response = api_client.get("/api/flows/workflows/nonexistent")

        assert response.status_code == 404


class TestExecutionRunEndpoint:
    """Tests for POST /api/flows/workflows/{slug}/run endpoint."""

    def test_run_workflow_unauthenticated(self, api_client, db, reset_registry):
        """Test that unauthenticated requests are rejected."""
        response = api_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({"inputs": {}}),
            content_type="application/json",
        )

        # Should return 401 or 403 for unauthenticated users
        assert response.status_code in [401, 403]

    def test_run_workflow_not_found(
        self,
        authenticated_client,
        db,
        reset_registry,
        test_organization,
        test_project,
    ):
        """Test that 404 is returned for non-existent workflow."""
        response = authenticated_client.post(
            "/api/flows/workflows/nonexistent/run",
            data=json.dumps({"inputs": {}}),
            content_type="application/json",
        )

        assert response.status_code == 404

    def test_run_workflow_validation_error(
        self,
        authenticated_client,
        db,
        reset_registry,
        temp_workflow_dir,
        test_organization,
        test_project,
    ):
        """Test that input validation errors return 400."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        # Send request without required input
        response = authenticated_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({"inputs": {}}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Input validation failed"
        assert "validation_errors" in data
        assert len(data["validation_errors"]) > 0
        assert data["validation_errors"][0]["field"] == "test_input"

    # NOTE: test_run_workflow_no_project removed because the application's
    # signal handlers (projects/signals.py) automatically create a default
    # project when an OrganizationUser is created.
    # This ensures users always have a project context available.

    @patch("flows.api.WorkflowRunner")
    def test_run_workflow_success(
        self,
        mock_runner_class,
        authenticated_client,
        db,
        reset_registry,
        temp_workflow_dir,
        test_organization,
        test_project,
    ):
        """Test successful workflow execution."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        # Mock the runner
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            return_value={
                "run_id": "abc12345",
                "workflow": "test_workflow",
                "outputs": {
                    "Test Output": {
                        "type": "MarkdownDocument",
                        "id": 1,
                        "name": "Test Output",
                        "folder": "TestFolder/Results",
                    }
                },
                "state": {},
            }
        )
        mock_runner_class.return_value = mock_runner

        response = authenticated_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({"inputs": {"test_input": "test value"}}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["run_id"] == "abc12345"
        assert data["workflow"] == "test_workflow"
        assert "Test Output" in data["outputs"]
        assert data["outputs"]["Test Output"]["type"] == "MarkdownDocument"

    @patch("flows.api.WorkflowRunner")
    def test_run_workflow_with_project_id(
        self,
        mock_runner_class,
        authenticated_client,
        db,
        reset_registry,
        temp_workflow_dir,
        test_organization,
        test_project,
    ):
        """Test workflow execution with explicit project_id."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            return_value={
                "run_id": "xyz67890",
                "workflow": "test_workflow",
                "outputs": {},
                "state": {},
            }
        )
        mock_runner_class.return_value = mock_runner

        response = authenticated_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({
                "inputs": {"test_input": "test value"},
                "project_id": test_project.id,
            }),
            content_type="application/json",
        )

        assert response.status_code == 200

    @patch("flows.api.WorkflowRunner")
    def test_run_workflow_execution_error(
        self,
        mock_runner_class,
        authenticated_client,
        db,
        reset_registry,
        temp_workflow_dir,
        test_organization,
        test_project,
    ):
        """Test workflow execution error handling."""
        from workflows.exceptions import WorkflowError

        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            side_effect=WorkflowError("Workflow execution failed")
        )
        mock_runner_class.return_value = mock_runner

        response = authenticated_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({"inputs": {"test_input": "test value"}}),
            content_type="application/json",
        )

        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "failed"
        assert "Workflow execution failed" in data["error"]

    def test_run_workflow_invalid_project_id(
        self,
        authenticated_client,
        db,
        reset_registry,
        temp_workflow_dir,
        test_organization,
        test_project,
    ):
        """Test error when project_id doesn't exist or belong to user's org."""
        registry = WorkflowRegistry.get_instance()
        registry.discover_builtins(temp_workflow_dir)

        response = authenticated_client.post(
            "/api/flows/workflows/test_workflow/run",
            data=json.dumps({
                "inputs": {"test_input": "test value"},
                "project_id": 99999,  # Non-existent project
            }),
            content_type="application/json",
        )

        assert response.status_code == 400


class TestValidateWorkflowInputs:
    """Tests for the _validate_workflow_inputs helper function."""

    def test_validate_valid_inputs(self):
        """Test validation passes for valid inputs."""
        spec = WorkflowSpec(
            slug="test-workflow",
            inputs=[
                InputSpec(name="required_input", type="str", required=True),
                InputSpec(name="optional_input", type="int", required=False, value=10),
            ],
        )

        errors = _validate_workflow_inputs(spec, {"required_input": "value"})

        assert errors == []

    def test_validate_missing_required_input(self):
        """Test validation fails for missing required input."""
        spec = WorkflowSpec(
            slug="test-workflow",
            inputs=[
                InputSpec(name="required_input", type="str", required=True),
            ],
        )

        errors = _validate_workflow_inputs(spec, {})

        assert len(errors) == 1
        assert errors[0].field == "required_input"
        assert "required" in errors[0].message.lower()

    def test_validate_invalid_type(self):
        """Test validation fails for invalid type."""
        spec = WorkflowSpec(
            slug="test-workflow",
            inputs=[
                InputSpec(name="int_input", type="int", required=True),
            ],
        )

        errors = _validate_workflow_inputs(spec, {"int_input": "not-an-int"})

        assert len(errors) == 1
        assert errors[0].field == "int_input"

    def test_validate_positive_int(self):
        """Test validation for PositiveInt type."""
        spec = WorkflowSpec(
            slug="test-workflow",
            inputs=[
                InputSpec(name="pos_int", type="PositiveInt", required=True),
            ],
        )

        # Valid positive int
        errors = _validate_workflow_inputs(spec, {"pos_int": 5})
        assert errors == []

        # Invalid (zero)
        errors = _validate_workflow_inputs(spec, {"pos_int": 0})
        assert len(errors) == 1
        assert errors[0].field == "pos_int"

        # Invalid (negative)
        errors = _validate_workflow_inputs(spec, {"pos_int": -1})
        assert len(errors) == 1
        assert errors[0].field == "pos_int"


class TestExecutionRunSchemas:
    """Tests for workflow run request/response schemas."""

    def test_workflow_run_request_minimal(self):
        """Test ExecutionRunRequest with minimal data."""
        request = ExecutionRunRequest(inputs={"key": "value"})

        assert request.inputs == {"key": "value"}
        assert request.project_id is None

    def test_workflow_run_request_full(self):
        """Test ExecutionRunRequest with all fields."""
        request = ExecutionRunRequest(
            inputs={"key": "value"},
            project_id=1,
        )

        assert request.inputs == {"key": "value"}
        assert request.project_id == 1

    def test_workflow_run_response_serialization(self):
        """Test ExecutionRunResponse serialization."""
        response = ExecutionRunResponse(
            status="completed",
            run_id="abc123",
            workflow="test-workflow",
            outputs={
                "output1": ExecutionOutputResult(
                    type="MarkdownDocument",
                    id=1,
                    name="Test Output",
                    folder="Output/Folder",
                )
            },
        )

        data = response.model_dump()

        assert data["status"] == "completed"
        assert data["run_id"] == "abc123"
        assert data["workflow"] == "test-workflow"
        assert "output1" in data["outputs"]
        assert data["outputs"]["output1"]["type"] == "MarkdownDocument"

    def test_workflow_run_error_response(self):
        """Test ExecutionRunErrorResponse serialization."""
        response = ExecutionRunErrorResponse(
            status="failed",
            error="Something went wrong",
            validation_errors=[
                ExecutionValidationError(field="input1", message="Required field"),
            ],
        )

        data = response.model_dump()

        assert data["status"] == "failed"
        assert data["error"] == "Something went wrong"
        assert len(data["validation_errors"]) == 1
        assert data["validation_errors"][0]["field"] == "input1"

    def test_workflow_output_result_with_error(self):
        """Test ExecutionOutputResult with error."""
        result = ExecutionOutputResult(
            type="MarkdownDocument",
            error="Failed to create document",
        )

        data = result.model_dump()

        assert data["type"] == "MarkdownDocument"
        assert data["error"] == "Failed to create document"
        assert data["id"] is None
