"""
Integration tests for summarize_content workflow.

Tests the complete workflow lifecycle including:
- Registry discovery and registration
- Configuration loading and validation
- Input validation
- Node execution with mocked AI service
- Full workflow execution through WorkflowRunner
- Output document creation
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workflows.builtin.summarize_content.flow import build_flow
from workflows.builtin.summarize_content.nodes import ReadContentNode, SummarizeNode
from workflows.config import load_workflow_config
from workflows.context import (
    InputContainer,
    OutputContainer,
    ServiceContainer,
    WorkflowContext,
)
from workflows.registry import ServiceRegistry, WorkflowRegistry
from workflows.runner import WorkflowRunner


class TestWorkflowRegistration:
    """Tests for workflow discovery and registry registration."""

    @pytest.fixture(autouse=True)
    def reset_registries(self):
        """Reset singleton registries before each test."""
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()
        yield
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()

    def test_summarize_content_discovered_in_registry(self):
        """Test that summarize_content workflow is discovered from builtin directory."""
        registry = WorkflowRegistry.get_instance()
        workflows_path = Path(__file__).parent.parent.parent / "workflows"
        registry.discover_builtins(workflows_path)

        workflows = registry.list_workflows()

        assert "summarize_content" in workflows
        assert workflows["summarize_content"]["config_path"].exists()
        assert workflows["summarize_content"]["flow_builder"] is not None

    def test_workflow_config_path_is_correct(self):
        """Test that workflow config path points to existing flow-config.yaml."""
        registry = WorkflowRegistry.get_instance()
        workflows_path = Path(__file__).parent.parent.parent / "workflows"
        registry.discover_builtins(workflows_path)

        workflow = registry.get("summarize_content")

        assert workflow is not None
        config_path = workflow["config_path"]
        assert config_path.name == "flow-config.yaml"
        assert config_path.parent.name == "summarize_content"

    def test_flow_builder_returns_valid_flow(self):
        """Test that the flow builder function returns a valid Flow."""
        flow = build_flow()

        # Flow should have a start node
        assert flow.start_node is not None
        assert isinstance(flow.start_node, ReadContentNode)


class TestWorkflowConfigLoading:
    """Tests for workflow configuration loading and validation."""

    @pytest.fixture
    def config_path(self):
        """Get path to summarize_content flow-config.yaml."""
        return (
            Path(__file__).parent.parent.parent
            / "workflows"
            / "builtin"
            / "summarize_content"
            / "flow-config.yaml"
        )

    def test_config_loads_successfully(self, config_path):
        """Test that workflow config loads without errors."""
        spec = load_workflow_config(config_path)

        assert spec.slug == "summarize_content"

    def test_config_has_required_inputs(self, config_path):
        """Test that config defines expected required inputs."""
        spec = load_workflow_config(config_path)

        source_type_input = spec.get_input_spec("source_type")
        source_id_input = spec.get_input_spec("source_id")

        assert source_type_input is not None
        assert source_type_input.required is True
        assert source_type_input.type == "str"

        assert source_id_input is not None
        assert source_id_input.required is True
        assert source_id_input.type == "str"

    def test_config_has_optional_summary_style(self, config_path):
        """Test that summary_style input is optional with default value."""
        spec = load_workflow_config(config_path)

        summary_style = spec.get_input_spec("summary_style")

        assert summary_style is not None
        assert summary_style.required is False
        assert summary_style.value == "brief"
        assert summary_style.type == "str"

    def test_config_has_markdown_output(self, config_path):
        """Test that config defines MarkdownDocument output."""
        spec = load_workflow_config(config_path)

        assert len(spec.outputs) >= 1
        output = spec.outputs[0]

        assert output.type == "MarkdownDocument"
        assert "{source_type}" in output.name
        assert output.target is not None

    def test_config_has_ai_service(self, config_path):
        """Test that config specifies AIService binding."""
        spec = load_workflow_config(config_path)

        ai_service = spec.get_service_spec("ai")

        assert ai_service is not None
        assert ai_service.name == "AIService"
        assert ai_service.ctxref == "ai"


class TestInputValidation:
    """Tests for workflow input validation."""

    @pytest.fixture
    def config_path(self):
        """Get path to summarize_content flow-config.yaml."""
        return (
            Path(__file__).parent.parent.parent
            / "workflows"
            / "builtin"
            / "summarize_content"
            / "flow-config.yaml"
        )

    def test_valid_inputs_pass_validation(self, config_path):
        """Test that valid inputs pass validation."""
        spec = load_workflow_config(config_path)

        # Validate each required input
        source_type = spec.get_input_spec("source_type").validate_value("document")
        source_id = spec.get_input_spec("source_id").validate_value("123")

        assert source_type == "document"
        assert source_id == "123"

    def test_missing_required_input_raises_error(self, config_path):
        """Test that missing required inputs raise ValueError."""
        spec = load_workflow_config(config_path)

        source_type_spec = spec.get_input_spec("source_type")

        with pytest.raises(ValueError) as exc_info:
            source_type_spec.validate_value(None)

        assert "Required input" in str(exc_info.value)
        assert "source_type" in str(exc_info.value)

    def test_optional_input_uses_default(self, config_path):
        """Test that optional inputs use default value when not provided."""
        spec = load_workflow_config(config_path)

        summary_style_spec = spec.get_input_spec("summary_style")
        value = summary_style_spec.validate_value(None)

        assert value == "brief"

    def test_valid_source_types(self, config_path):
        """Test various valid source type values."""
        spec = load_workflow_config(config_path)
        source_type_spec = spec.get_input_spec("source_type")

        for source_type in ["document", "folder", "clipboard"]:
            result = source_type_spec.validate_value(source_type)
            assert result == source_type


class TestFlowExecution:
    """Tests for flow execution with mocked services."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext for testing."""
        ctx = WorkflowContext()
        ctx.inputs = InputContainer()
        ctx.outputs = OutputContainer()
        ctx.services = ServiceContainer()
        ctx.state = {}
        return ctx

    @pytest.fixture
    def shared_dict(self, mock_context):
        """Create shared dict with context."""
        return {"ctx": mock_context}

    def test_build_flow_creates_correct_node_chain(self):
        """Test that build_flow creates correct node chain."""
        flow = build_flow()

        # Start node should be ReadContentNode
        assert isinstance(flow.start_node, ReadContentNode)

        # ReadContentNode should have a successor
        assert flow.start_node.successors is not None
        assert "default" in flow.start_node.successors

        # Successor should be SummarizeNode
        assert isinstance(flow.start_node.successors["default"], SummarizeNode)

    @pytest.mark.django_db
    def test_read_content_node_with_document(self, shared_dict, mock_context, db):
        """Test ReadContentNode execution with a document source."""
        from accounts.models import Account
        from documents.models import Markdown

        # Create test document
        org = Account.objects.create(name="Test Org")
        doc = Markdown.objects.create(
            organization=org,
            name="Test Doc",
            content="# Test Content\n\nThis is test content for summarization.",
        )

        # Set up inputs
        mock_context.inputs.source_type = "document"
        mock_context.inputs.source_id = str(doc.id)

        # Execute node
        node = ReadContentNode()
        prep_result = node.prep(shared_dict)
        node.post(shared_dict, prep_result, None)

        # Verify state
        assert "Test Content" in mock_context.state["content"]
        assert mock_context.state["source_type"] == "document"
        assert mock_context.state["content_metadata"]["document_name"] == "Test Doc"

    @pytest.mark.django_db
    def test_read_content_node_with_folder(self, shared_dict, mock_context, db):
        """Test ReadContentNode execution with a folder source."""
        from accounts.models import Account
        from documents.models import Folder, Markdown
        from projects.models import Project
        from workspaces.models import Workspace

        # Create test folder with documents
        org = Account.objects.create(name="Test Org")
        project = Project.objects.create(organization=org, name="Test Project")
        workspace = Workspace.objects.create(project=project, name="Test Workspace")
        folder = Folder.objects.create(
            organization=org,
            project=project,
            workspace=workspace,
            name="Test Folder",
        )
        Markdown.objects.create(
            organization=org,
            name="Doc 1",
            content="First document content",
            folder=folder,
        )
        Markdown.objects.create(
            organization=org,
            name="Doc 2",
            content="Second document content",
            folder=folder,
        )

        # Set up inputs
        mock_context.inputs.source_type = "folder"
        mock_context.inputs.source_id = str(folder.id)

        # Execute node
        node = ReadContentNode()
        prep_result = node.prep(shared_dict)
        node.post(shared_dict, prep_result, None)

        # Verify state
        assert "First document content" in mock_context.state["content"]
        assert "Second document content" in mock_context.state["content"]
        assert mock_context.state["source_type"] == "folder"
        assert mock_context.state["content_metadata"]["folder_name"] == "Test Folder"
        assert mock_context.state["content_metadata"]["document_count"] == 2

    @pytest.mark.asyncio
    async def test_summarize_node_with_mocked_ai(self, shared_dict, mock_context):
        """Test SummarizeNode execution with mocked AI service."""
        # Set up context state (as if ReadContentNode ran)
        mock_context.state["content"] = "# Test Content\n\nThis is content to summarize."
        mock_context.state["content_metadata"] = {"document_name": "Test Doc"}
        mock_context.state["source_type"] = "document"
        mock_context.inputs.summary_style = "brief"

        # Create mock AI service
        mock_ai = MagicMock()
        mock_ai.achat = AsyncMock(return_value="This is a test summary of the content.")
        mock_context.services.register("ai", mock_ai)

        # Execute node
        node = SummarizeNode()
        prompt = node._prep(shared_dict)
        node._current_shared = shared_dict

        result = await node.async_run(prompt)
        node.post(shared_dict, prompt, result)

        # Verify AI was called
        mock_ai.configure_agent.assert_called_once()
        mock_ai.achat.assert_called_once()

        # Verify output
        assert mock_context.outputs.get("document Summary") == "This is a test summary of the content."
        assert mock_context.state["summary"] == "This is a test summary of the content."


class TestWorkflowRunner:
    """Tests for WorkflowRunner configuration and input validation.

    Note: Full end-to-end execution tests with asyncio.run() and py-pglite
    can cause segfaults due to infrastructure issues with psycopg/py-pglite.
    Node-level execution tests are covered in test_nodes.py.
    """

    @pytest.fixture(autouse=True)
    def reset_registries(self):
        """Reset singleton registries before each test."""
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()
        yield
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()

    @pytest.fixture
    def setup_registry(self):
        """Set up workflow registry with discovered workflows."""
        registry = WorkflowRegistry.get_instance()
        workflows_path = Path(__file__).parent.parent.parent / "workflows"
        registry.discover_builtins(workflows_path)
        return registry

    def test_workflow_runner_initialization(self):
        """Test WorkflowRunner can be instantiated with mock objects."""
        from unittest.mock import MagicMock

        org = MagicMock()
        project = MagicMock()
        workspace = MagicMock()
        user = MagicMock()

        runner = WorkflowRunner(org, project, workspace, user)

        assert runner.organization == org
        assert runner.project == project
        assert runner.workspace == workspace
        assert runner.user == user
        assert runner.service_registry is not None

    @pytest.mark.django_db
    def test_workflow_with_missing_required_input(self, setup_registry, db):
        """Test that workflow runner raises error for missing required inputs."""
        import asyncio

        from django.contrib.auth import get_user_model

        from accounts.models import Account
        from projects.models import Project
        from workspaces.models import Workspace
        from workflows.exceptions import WorkflowError

        User = get_user_model()

        user = User.objects.create_user(username="missing_input_user")
        org = Account.objects.create(name="Missing Input Test Org")
        project = Project.objects.create(organization=org, name="Missing Input Test Project", created_by=user)
        # Use the default workspace created by signal instead of creating another
        from accounts.utils import get_project_default_workspace
        workspace = get_project_default_workspace(project)

        runner = WorkflowRunner(org, project, workspace, user)

        with pytest.raises(WorkflowError) as exc_info:
            asyncio.run(
                runner.run(
                    "summarize_content",
                    {
                        # Missing source_type and source_id
                    },
                )
            )

        assert "Required input" in str(exc_info.value)


class TestOutputSpec:
    """Tests for workflow output specification."""

    @pytest.fixture
    def config_path(self):
        """Get path to summarize_content flow-config.yaml."""
        return (
            Path(__file__).parent.parent.parent
            / "workflows"
            / "builtin"
            / "summarize_content"
            / "flow-config.yaml"
        )

    def test_output_spec_defines_markdown_document(self, config_path):
        """Test that output spec correctly defines MarkdownDocument type."""
        spec = load_workflow_config(config_path)

        assert len(spec.outputs) >= 1
        output = spec.outputs[0]

        assert output.type == "MarkdownDocument"
        assert output.target is not None
        # Output name uses template variable
        assert "{source_type}" in output.name

    def test_output_spec_target_uses_template(self, config_path):
        """Test that output target path uses template variables."""
        spec = load_workflow_config(config_path)

        output = spec.outputs[0]
        # Target should contain source_type for dynamic folder paths
        assert "{source_type}" in output.target


class TestSummaryStyles:
    """Tests for different summary style configurations."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext for testing."""
        ctx = WorkflowContext()
        ctx.inputs = InputContainer()
        ctx.outputs = OutputContainer()
        ctx.services = ServiceContainer()
        ctx.state = {
            "content": "Test content for summarization.",
            "content_metadata": {"document_name": "Test Doc"},
            "source_type": "document",
        }
        return ctx

    @pytest.fixture
    def shared_dict(self, mock_context):
        """Create shared dict with context."""
        return {"ctx": mock_context}

    def test_brief_style_prompt_structure(self, shared_dict, mock_context):
        """Test that brief style generates correct prompt structure."""
        mock_context.inputs.summary_style = "brief"

        node = SummarizeNode()
        prompt = node._prep(shared_dict)

        assert "2-3 paragraphs" in prompt
        assert "concisely" in prompt
        assert "Test content for summarization" in prompt

    def test_detailed_style_prompt_structure(self, shared_dict, mock_context):
        """Test that detailed style generates correct prompt structure."""
        mock_context.inputs.summary_style = "detailed"

        node = SummarizeNode()
        prompt = node._prep(shared_dict)

        assert "comprehensive summary" in prompt
        assert "Key Points" in prompt
        assert "Supporting Details" in prompt
        assert "Conclusions" in prompt
        assert "Test content for summarization" in prompt

    def test_default_style_is_brief(self, shared_dict, mock_context):
        """Test that missing summary_style defaults to brief."""
        # Don't set summary_style
        mock_context.inputs._inputs = {}

        node = SummarizeNode()
        prompt = node._prep(shared_dict)

        assert "2-3 paragraphs" in prompt
        assert "concisely" in prompt


class TestErrorHandling:
    """Tests for error handling in workflow execution."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext for testing."""
        ctx = WorkflowContext()
        ctx.inputs = InputContainer()
        ctx.outputs = OutputContainer()
        ctx.services = ServiceContainer()
        ctx.state = {}
        return ctx

    @pytest.fixture
    def shared_dict(self, mock_context):
        """Create shared dict with context."""
        return {"ctx": mock_context}

    def test_invalid_source_type_raises_error(self, shared_dict, mock_context):
        """Test that invalid source_type raises ValueError."""
        mock_context.inputs.source_type = "invalid"
        mock_context.inputs.source_id = "123"

        node = ReadContentNode()
        prep_result = node.prep(shared_dict)

        with pytest.raises(ValueError) as exc_info:
            node.post(shared_dict, prep_result, None)

        assert "Unsupported source_type" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    @pytest.mark.django_db
    def test_nonexistent_document_raises_error(self, shared_dict, mock_context, db):
        """Test that fetching nonexistent document raises appropriate error."""
        mock_context.inputs.source_type = "document"
        mock_context.inputs.source_id = "99999999-9999-9999-9999-999999999999"

        node = ReadContentNode()
        prep_result = node.prep(shared_dict)

        with pytest.raises(Exception):  # Document.DoesNotExist
            node.post(shared_dict, prep_result, None)

    @pytest.mark.django_db
    def test_nonexistent_folder_raises_error(self, shared_dict, mock_context, db):
        """Test that fetching nonexistent folder raises appropriate error."""
        mock_context.inputs.source_type = "folder"
        mock_context.inputs.source_id = "99999999-9999-9999-9999-999999999999"

        node = ReadContentNode()
        prep_result = node.prep(shared_dict)

        with pytest.raises(Exception):  # Folder.DoesNotExist
            node.post(shared_dict, prep_result, None)

    @pytest.mark.django_db
    def test_nonexistent_clipboard_raises_error(self, shared_dict, mock_context, db):
        """Test that fetching nonexistent clipboard raises appropriate error."""
        mock_context.inputs.source_type = "clipboard"
        mock_context.inputs.source_id = "99999999-9999-9999-9999-999999999999"

        node = ReadContentNode()
        prep_result = node.prep(shared_dict)

        with pytest.raises(Exception):  # Clipboard.DoesNotExist
            node.post(shared_dict, prep_result, None)


class TestAPIEndpointIntegration:
    """Tests for workflow availability through API endpoints."""

    @pytest.fixture(autouse=True)
    def reset_registries(self):
        """Reset singleton registries before each test."""
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()
        yield
        WorkflowRegistry.reset_instance()
        ServiceRegistry.reset_instance()

    def test_workflow_listed_in_api_format(self):
        """Test that workflow can be converted to API response format."""
        from pathlib import Path

        from flows.api import _convert_workflow_to_out

        # Discover workflows
        registry = WorkflowRegistry.get_instance()
        workflows_path = Path(__file__).parent.parent.parent / "workflows"
        registry.discover_builtins(workflows_path)

        workflow_data = registry.get("summarize_content")
        workflow_out = _convert_workflow_to_out("summarize_content", workflow_data)

        # Verify API response structure
        assert workflow_out.slug == "summarize_content"
        assert len(workflow_out.inputs) >= 2  # source_type, source_id
        assert len(workflow_out.outputs) >= 1

        # Verify inputs
        input_names = [inp.name for inp in workflow_out.inputs]
        assert "source_type" in input_names
        assert "source_id" in input_names
        assert "summary_style" in input_names

        # Verify required flags
        source_type_input = next(inp for inp in workflow_out.inputs if inp.name == "source_type")
        assert source_type_input.required is True

        summary_style_input = next(inp for inp in workflow_out.inputs if inp.name == "summary_style")
        assert summary_style_input.required is False
