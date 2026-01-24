"""
Tests for summarize_content workflow nodes.

Tests the ReadContentNode and SummarizeNode implementations including:
- Document content fetching
- Folder content aggregation
- Clipboard content retrieval
- Brief and detailed summary prompt generation
- Error handling for invalid source types
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workflows.builtin.summarize_content.nodes import ReadContentNode, SummarizeNode
from workflows.context import InputContainer, OutputContainer, ServiceContainer, WorkflowContext


class TestReadContentNode:
    """Tests for ReadContentNode content fetching logic."""

    @pytest.fixture
    def node(self):
        """Create a ReadContentNode instance."""
        return ReadContentNode()

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext with inputs."""
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

    def test_prep_extracts_source_params(self, node, shared_dict, mock_context):
        """Test that prep() extracts source_type and source_id from inputs."""
        mock_context.inputs.source_type = "document"
        mock_context.inputs.source_id = "123"

        result = node.prep(shared_dict)

        assert result == {"source_type": "document", "source_id": "123"}

    @pytest.mark.django_db
    def test_fetch_document_content_text_document(self, node, mock_context, db):
        """Test fetching content from a TextDocument (Markdown)."""
        from accounts.models import Account
        from documents.models import Markdown

        # Create test data
        org = Account.objects.create(name="Test Org")
        doc = Markdown.objects.create(
            organization=org,
            name="Test Document",
            content="# Hello World\n\nThis is test content.",
        )

        result = node._fetch_document_content(str(doc.id), mock_context)

        assert "Test Document" in result["content"]
        assert "Hello World" in result["content"]
        assert result["metadata"]["document_name"] == "Test Document"
        assert result["metadata"]["document_type"] == "Markdown"

    @pytest.mark.django_db
    def test_fetch_document_content_non_text_document(self, node, mock_context, db):
        """Test fetching content from a non-text document (Image)."""
        from accounts.models import Account
        from documents.models import Image

        org = Account.objects.create(name="Test Org")
        # Create Image document (requires image_file, so we mock it)
        with patch.object(Image, "save", lambda self, *args, **kwargs: None):
            doc = Image(
                organization=org,
                name="Test Image",
            )
            doc.id = 999  # Set a fake ID for testing
            doc.pk = 999

        # Mock the document lookup
        with patch("documents.models.Document.objects") as mock_objects:
            mock_qs = MagicMock()
            mock_objects.select_subclasses.return_value = mock_qs
            mock_qs.filter.return_value = mock_qs  # filter() returns queryset
            mock_qs.get.return_value = doc

            result = node._fetch_document_content("999", mock_context)

        assert "Test Image" in result["content"]
        assert "content not available for summarization" in result["content"]
        assert result["metadata"]["document_name"] == "Test Image"
        assert result["metadata"]["document_type"] == "Image"

    @pytest.mark.django_db
    def test_fetch_folder_content_with_documents(self, node, mock_context, db):
        """Test fetching content from a folder with multiple documents."""
        from accounts.models import Account
        from documents.models import Folder, Markdown
        from projects.models import Project

        # Create org, project, folder hierarchy
        org = Account.objects.create(name="Test Org")
        project = Project.objects.create(organization=org, name="Test Project")
        folder = Folder.objects.create(
            organization=org,
            project=project,
            name="Test Folder",
        )

        # Create documents in folder
        Markdown.objects.create(
            organization=org,
            name="Doc 1",
            content="Content of document 1",
            folder=folder,
        )
        Markdown.objects.create(
            organization=org,
            name="Doc 2",
            content="Content of document 2",
            folder=folder,
        )

        result = node._fetch_folder_content(str(folder.id), mock_context)

        assert "Doc 1" in result["content"]
        assert "Doc 2" in result["content"]
        assert "Content of document 1" in result["content"]
        assert "Content of document 2" in result["content"]
        assert result["metadata"]["folder_name"] == "Test Folder"
        assert result["metadata"]["document_count"] == 2
        assert "Doc 1" in result["metadata"]["document_names"]
        assert "Doc 2" in result["metadata"]["document_names"]

    @pytest.mark.django_db
    def test_fetch_folder_content_empty_folder(self, node, mock_context, db):
        """Test fetching content from an empty folder."""
        from accounts.models import Account
        from documents.models import Folder
        from projects.models import Project

        org = Account.objects.create(name="Test Org")
        project = Project.objects.create(organization=org, name="Test Project")
        folder = Folder.objects.create(
            organization=org,
            project=project,
            name="Empty Folder",
        )

        result = node._fetch_folder_content(str(folder.id), mock_context)

        assert "No documents found in folder" in result["content"]
        assert result["metadata"]["folder_name"] == "Empty Folder"
        assert result["metadata"]["document_count"] == 0

    def test_post_invalid_source_type(self, node, shared_dict, mock_context):
        """Test that post() raises ValueError for invalid source_type."""
        mock_context.inputs.source_type = "invalid"
        mock_context.inputs.source_id = "123"

        prep_res = {"source_type": "invalid", "source_id": "123"}

        with pytest.raises(ValueError) as exc_info:
            node.post(shared_dict, prep_res, None)

        assert "Unsupported source_type" in str(exc_info.value)
        assert "invalid" in str(exc_info.value)

    @pytest.mark.django_db
    def test_post_document_source_type(self, node, shared_dict, mock_context, db):
        """Test post() with document source type stores content in state."""
        from accounts.models import Account
        from documents.models import Markdown

        org = Account.objects.create(name="Test Org")
        doc = Markdown.objects.create(
            organization=org,
            name="Post Test Doc",
            content="Post test content",
        )

        mock_context.inputs.source_type = "document"
        mock_context.inputs.source_id = str(doc.id)

        prep_res = {"source_type": "document", "source_id": str(doc.id)}
        result = node.post(shared_dict, prep_res, None)

        assert result == "default"
        assert "Post test content" in mock_context.state["content"]
        assert mock_context.state["source_type"] == "document"
        assert mock_context.state["source_id"] == str(doc.id)
        assert "content_metadata" in mock_context.state


class TestSummarizeNode:
    """Tests for SummarizeNode AI summarization logic."""

    @pytest.fixture
    def node(self):
        """Create a SummarizeNode instance."""
        return SummarizeNode()

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext with state and inputs."""
        ctx = WorkflowContext()
        ctx.inputs = InputContainer()
        ctx.outputs = OutputContainer()
        ctx.services = ServiceContainer()
        ctx.state = {
            "content": "# Test Content\n\nThis is some test content to summarize.",
            "content_metadata": {"document_name": "Test Doc"},
            "source_type": "document",
        }
        return ctx

    @pytest.fixture
    def shared_dict(self, mock_context):
        """Create shared dict with context."""
        return {"ctx": mock_context}

    def test_prep_brief_style(self, node, shared_dict, mock_context):
        """Test that _prep() builds correct prompt for brief style."""
        mock_context.inputs.summary_style = "brief"

        prompt = node._prep(shared_dict)

        assert "2-3 paragraphs" in prompt
        assert "concisely" in prompt
        assert "Test Content" in prompt
        assert "Test Doc" in prompt

    def test_prep_detailed_style(self, node, shared_dict, mock_context):
        """Test that _prep() builds correct prompt for detailed style."""
        mock_context.inputs.summary_style = "detailed"

        prompt = node._prep(shared_dict)

        assert "comprehensive summary" in prompt
        assert "Key Points" in prompt
        assert "Supporting Details" in prompt
        assert "Conclusions" in prompt
        assert "Test Content" in prompt

    def test_prep_default_style_is_brief(self, node, shared_dict, mock_context):
        """Test that default summary style is brief."""
        # Don't set summary_style - should default to brief
        mock_context.inputs._inputs = {}

        prompt = node._prep(shared_dict)

        assert "2-3 paragraphs" in prompt
        assert "concisely" in prompt

    def test_prep_includes_folder_context(self, node, shared_dict, mock_context):
        """Test that _prep() includes folder context in prompt."""
        mock_context.state["content_metadata"] = {
            "folder_name": "My Folder",
            "document_count": 5,
        }

        prompt = node._prep(shared_dict)

        assert "Folder 'My Folder'" in prompt
        assert "5 document(s)" in prompt

    def test_prep_includes_clipboard_context(self, node, shared_dict, mock_context):
        """Test that _prep() includes clipboard context in prompt."""
        mock_context.state["content_metadata"] = {
            "clipboard_name": "My Clipboard",
            "item_count": 3,
        }

        prompt = node._prep(shared_dict)

        assert "Clipboard 'My Clipboard'" in prompt
        assert "3 item(s)" in prompt

    @pytest.mark.asyncio
    async def test_async_run_calls_ai_service(self, node):
        """Test that async_run() calls the AI service correctly."""
        mock_ai = MagicMock()
        mock_ai.achat = AsyncMock(return_value="This is the summary")

        # Set up the stored shared reference
        ctx = WorkflowContext()
        ctx.services = ServiceContainer()
        ctx.services.register("ai", mock_ai)
        node._current_shared = {"ctx": ctx}

        result = await node.async_run("Test prompt")

        assert result == "This is the summary"
        mock_ai.configure_agent.assert_called_once()
        mock_ai.achat.assert_called_once_with("Test prompt")

    def test_post_sets_output(self, node, shared_dict, mock_context):
        """Test that post() sets the output correctly."""
        run_res = "This is the generated summary."

        result = node.post(shared_dict, "prompt", run_res)

        assert result == "default"
        assert mock_context.outputs.get("document Summary") == run_res
        assert mock_context.state["summary"] == run_res

    def test_post_uses_source_type_in_output_name(self, node, shared_dict, mock_context):
        """Test that post() uses source_type in output name."""
        mock_context.state["source_type"] = "folder"
        run_res = "Folder summary"

        node.post(shared_dict, "prompt", run_res)

        assert mock_context.outputs.get("folder Summary") == run_res


class TestReadContentNodeIntegration:
    """Integration tests for ReadContentNode with real database operations."""

    @pytest.fixture
    def node(self):
        """Create a ReadContentNode instance."""
        return ReadContentNode()

    @pytest.fixture
    def mock_context(self):
        """Create a mock WorkflowContext."""
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

    @pytest.mark.django_db
    def test_full_document_flow(self, node, shared_dict, mock_context, db):
        """Test complete flow from prep to post for document source."""
        from accounts.models import Account
        from documents.models import Markdown

        org = Account.objects.create(name="Integration Org")
        doc = Markdown.objects.create(
            organization=org,
            name="Integration Doc",
            content="# Integration Test\n\nThis is integration test content.",
        )

        mock_context.inputs.source_type = "document"
        mock_context.inputs.source_id = str(doc.id)

        # Run prep
        prep_res = node.prep(shared_dict)
        assert prep_res["source_type"] == "document"
        assert prep_res["source_id"] == str(doc.id)

        # Run post
        result = node.post(shared_dict, prep_res, None)

        assert result == "default"
        assert "Integration Test" in mock_context.state["content"]
        assert mock_context.state["content_metadata"]["document_name"] == "Integration Doc"

    @pytest.mark.django_db
    def test_full_folder_flow(self, node, shared_dict, mock_context, db):
        """Test complete flow from prep to post for folder source."""
        from accounts.models import Account
        from documents.models import Folder, Markdown
        from projects.models import Project

        org = Account.objects.create(name="Folder Org")
        project = Project.objects.create(organization=org, name="Folder Project")
        folder = Folder.objects.create(
            organization=org,
            project=project,
            name="Integration Folder",
        )

        Markdown.objects.create(
            organization=org,
            name="Folder Doc 1",
            content="First document content",
            folder=folder,
        )
        Markdown.objects.create(
            organization=org,
            name="Folder Doc 2",
            content="Second document content",
            folder=folder,
        )

        mock_context.inputs.source_type = "folder"
        mock_context.inputs.source_id = str(folder.id)

        prep_res = node.prep(shared_dict)
        result = node.post(shared_dict, prep_res, None)

        assert result == "default"
        assert "First document content" in mock_context.state["content"]
        assert "Second document content" in mock_context.state["content"]
        assert mock_context.state["content_metadata"]["document_count"] == 2


class TestSummarizeNodePromptTemplates:
    """Tests for SummarizeNode prompt template constants."""

    def test_brief_instruction_contains_key_phrases(self):
        """Test that BRIEF_INSTRUCTION contains expected phrases."""
        assert "2-3 paragraphs" in SummarizeNode.BRIEF_INSTRUCTION
        assert "concisely" in SummarizeNode.BRIEF_INSTRUCTION
        assert "essential" in SummarizeNode.BRIEF_INSTRUCTION

    def test_detailed_instruction_contains_structure(self):
        """Test that DETAILED_INSTRUCTION contains expected structure."""
        assert "Overview" in SummarizeNode.DETAILED_INSTRUCTION
        assert "Key Points" in SummarizeNode.DETAILED_INSTRUCTION
        assert "Supporting Details" in SummarizeNode.DETAILED_INSTRUCTION
        assert "Conclusions" in SummarizeNode.DETAILED_INSTRUCTION
