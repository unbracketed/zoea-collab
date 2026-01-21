"""
Tests for agent tools.

These tests verify tool registration, instantiation, and basic functionality.
Integration tests requiring external APIs are marked with pytest.mark.integration.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.models import ProjectToolConfig
from agents.registry import ToolRegistry
from agents.tools.base import (
    ARTIFACT_OUTPUT_SCHEMA,
    OutputCollection,
    ToolArtifact,
    ZoeaTool,
    create_artifact_output,
    extract_artifacts_from_output,
)
from agents.tools.output_collections import (
    ConversationArtifactCollection,
    InMemoryArtifactCollection,
)


class TestZoeaTool:
    """Tests for ZoeaTool base class."""

    def test_zoea_tool_with_output_collection(self):
        """ZoeaTool should support output collection for artifact creation."""
        # Create a concrete subclass for testing
        class TestTool(ZoeaTool):
            name = "test_tool"
            description = "Test tool"
            inputs = {"query": {"type": "string", "description": "Test query"}}
            output_type = "string"

            def forward(self, query: str) -> str:
                self.create_artifact(
                    type="image",
                    path="/test/image.png",
                    mime_type="image/png",
                    title="Test Image",
                )
                return f"Processed: {query}"

        collection = InMemoryArtifactCollection()
        tool = TestTool(output_collection=collection)

        # Run the tool
        result = tool.forward("test query")

        # Verify artifact was created
        assert result == "Processed: test query"
        assert len(collection.artifacts) == 1
        artifact = collection.artifacts[0]
        assert artifact.type == "image"
        assert artifact.path == "/test/image.png"
        assert artifact.mime_type == "image/png"
        assert artifact.title == "Test Image"

    def test_zoea_tool_without_collection(self):
        """ZoeaTool should work without output collection (artifacts ignored)."""
        class TestTool(ZoeaTool):
            name = "test_tool"
            description = "Test tool"
            inputs = {"query": {"type": "string", "description": "Test query"}}
            output_type = "string"

            def forward(self, query: str) -> str:
                created = self.create_artifact(
                    type="image",
                    path="/test/image.png",
                )
                return f"Created: {created}"

        tool = TestTool()  # No output collection

        result = tool.forward("test")
        assert result == "Created: False"  # No collection, so returns False
        assert not tool.has_output_collection()

    def test_zoea_tool_collection_setter(self):
        """ZoeaTool should allow setting output collection after init."""
        class TestTool(ZoeaTool):
            name = "test_tool"
            description = "Test"
            inputs = {}
            output_type = "string"

            def forward(self) -> str:
                return "test"

        tool = TestTool()
        assert tool.output_collection is None

        collection = InMemoryArtifactCollection()
        tool.output_collection = collection

        assert tool.output_collection is collection
        assert tool.has_output_collection()

    def test_zoea_tool_telemetry(self):
        """ZoeaTool should include TelemetryMixin functionality."""
        class TestTool(ZoeaTool):
            name = "test_tool"
            description = "Test"
            inputs = {}
            output_type = "string"

            def forward(self) -> str:
                return "test"

        tool = TestTool()
        assert hasattr(tool, "telemetry")
        assert tool.telemetry["calls"] == 0

        # Record a call
        tool.record_call(0.5)
        assert tool.telemetry["calls"] == 1
        assert tool.telemetry["total_duration_s"] == 0.5


class TestOutputCollections:
    """Tests for OutputCollection implementations."""

    def test_in_memory_collection_basic(self):
        """InMemoryArtifactCollection should store artifacts."""
        collection = InMemoryArtifactCollection(context_id="test")

        artifact = ToolArtifact(
            type="image",
            path="/path/to/image.png",
            mime_type="image/png",
            title="Test Image",
        )
        collection.add_artifact(artifact)

        assert len(collection) == 1
        assert collection.artifacts[0] is artifact
        assert collection.context_id == "test"

    def test_in_memory_collection_clear(self):
        """InMemoryArtifactCollection.clear() should remove all artifacts."""
        collection = InMemoryArtifactCollection()
        collection.add_artifact(ToolArtifact(type="image", path="/a.png"))
        collection.add_artifact(ToolArtifact(type="code", path="/b.py"))

        assert len(collection) == 2
        collection.clear()
        assert len(collection) == 0

    def test_in_memory_collection_iteration(self):
        """InMemoryArtifactCollection should be iterable."""
        collection = InMemoryArtifactCollection()
        collection.add_artifact(ToolArtifact(type="image", path="/a.png"))
        collection.add_artifact(ToolArtifact(type="code", path="/b.py"))

        paths = [a.path for a in collection]
        assert paths == ["/a.png", "/b.py"]

    def test_conversation_artifact_collection(self):
        """ConversationArtifactCollection should track conversation context."""
        collection = ConversationArtifactCollection(conversation_id=123)

        assert collection.conversation_id == 123
        assert collection.conversation is None  # No model instance provided

        artifact = ToolArtifact(type="markdown", path="_inline_abc", content="# Test")
        collection.add_artifact(artifact)

        assert len(collection) == 1
        assert collection.artifacts[0].content == "# Test"

    def test_tool_artifact_dataclass(self):
        """ToolArtifact should have expected fields."""
        artifact = ToolArtifact(
            type="image",
            path="/media/img.png",
            mime_type="image/png",
            title="Generated Image",
            language=None,
            content=None,
            metadata={"source": "gemini"},
        )

        assert artifact.type == "image"
        assert artifact.path == "/media/img.png"
        assert artifact.mime_type == "image/png"
        assert artifact.title == "Generated Image"
        assert artifact.metadata == {"source": "gemini"}

    def test_output_collection_protocol(self):
        """InMemoryArtifactCollection should satisfy OutputCollection protocol."""
        collection = InMemoryArtifactCollection()
        assert isinstance(collection, OutputCollection)


class TestToolRegistry:
    """Tests for ToolRegistry singleton and tool registration."""

    def setup_method(self):
        """Reset registry before each test."""
        ToolRegistry.reset_instance()

    def test_singleton_pattern(self):
        """Registry should return same instance."""
        registry1 = ToolRegistry.get_instance()
        registry2 = ToolRegistry.get_instance()
        assert registry1 is registry2

    def test_builtin_tools_registered(self):
        """Built-in tools should be automatically registered."""
        registry = ToolRegistry.get_instance()
        tools = registry.list_tools()
        tool_names = [t.name for t in tools]

        # Core tools should be registered
        assert "web_search" in tool_names
        assert "visit_webpage" in tool_names
        assert "summarize_webpage" in tool_names
        assert "sports_news" in tool_names
        assert "image_analyzer" in tool_names

    def test_tool_definition_by_name(self):
        """Should retrieve tool definition by name."""
        registry = ToolRegistry.get_instance()
        definition = registry.get_tool_definition("web_search")

        assert definition is not None
        assert definition.name == "web_search"
        assert definition.category == "search"
        assert definition.default_enabled is True

    def test_nonexistent_tool_returns_none(self):
        """Should return None for unknown tool."""
        registry = ToolRegistry.get_instance()
        definition = registry.get_tool_definition("nonexistent_tool")
        assert definition is None


class TestWebSearchTool:
    """Tests for WebSearchTool."""

    def test_tool_instantiation(self):
        """Tool should instantiate without errors."""
        from agents.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        assert tool.name == "web_search"
        assert tool.max_results == 5  # Default

    def test_tool_with_custom_params(self):
        """Tool should accept custom parameters."""
        from agents.tools.web_search import WebSearchTool

        tool = WebSearchTool(max_results=10, rate_limit=2.0)
        assert tool.max_results == 10
        assert tool.rate_limit == 2.0

    def test_telemetry_initialized(self):
        """Tool should initialize telemetry dict."""
        from agents.tools.web_search import WebSearchTool

        tool = WebSearchTool()
        assert "calls" in tool.telemetry
        assert "errors" in tool.telemetry
        assert tool.telemetry["calls"] == 0


class TestVisitWebpageTool:
    """Tests for VisitWebpageTool."""

    def test_tool_instantiation(self):
        """Tool should instantiate without errors."""
        from agents.tools.visit_webpage import VisitWebpageTool

        tool = VisitWebpageTool()
        assert tool.name == "visit_webpage"
        assert tool.max_output_length == 40000  # Default
        assert tool.timeout == 20  # Default

    def test_tool_with_custom_params(self):
        """Tool should accept custom parameters."""
        from agents.tools.visit_webpage import VisitWebpageTool

        tool = VisitWebpageTool(max_output_length=10000, timeout=30)
        assert tool.max_output_length == 10000
        assert tool.timeout == 30

    def test_telemetry_initialized(self):
        """Tool should initialize telemetry dict."""
        from agents.tools.visit_webpage import VisitWebpageTool

        tool = VisitWebpageTool()
        assert "calls" in tool.telemetry
        assert "errors" in tool.telemetry
        assert tool.telemetry["calls"] == 0

    def test_invalid_url_returns_error(self):
        """Tool should return error for invalid URLs."""
        from agents.tools.visit_webpage import VisitWebpageTool

        tool = VisitWebpageTool()
        result = tool.forward("not-a-valid-url")
        assert "Error" in result
        assert "Invalid URL" in result

    def test_empty_url_returns_error(self):
        """Tool should return error for empty URL."""
        from agents.tools.visit_webpage import VisitWebpageTool

        tool = VisitWebpageTool()
        result = tool.forward("")
        assert "Error" in result
        assert "No URL" in result


class TestSportsNewsTool:
    """Tests for SportsNewsTool."""

    def test_tool_instantiation(self):
        """Tool should instantiate without errors."""
        from agents.tools.sports_news import SportsNewsTool

        tool = SportsNewsTool()
        assert tool.name == "sports_news"
        assert tool.timeout == 15  # Default

    def test_supported_sports(self):
        """Tool should support major sports leagues."""
        from agents.tools.sports_news import SportsNewsTool

        tool = SportsNewsTool()
        assert "nba" in tool.SPORT_CONFIG
        assert "nfl" in tool.SPORT_CONFIG
        assert "nhl" in tool.SPORT_CONFIG

    def test_invalid_sport_returns_error(self):
        """Tool should return error for invalid sport."""
        from agents.tools.sports_news import SportsNewsTool

        tool = SportsNewsTool()
        result = tool.forward(sport="invalid_sport", query_type="today")
        assert "Error" in result
        assert "Unknown sport" in result

    def test_invalid_query_type_returns_error(self):
        """Tool should return error for invalid query type."""
        from agents.tools.sports_news import SportsNewsTool

        tool = SportsNewsTool()
        result = tool.forward(sport="nba", query_type="invalid_type")
        assert "Error" in result
        assert "Unknown query_type" in result

    def test_telemetry_initialized(self):
        """Tool should initialize telemetry dict."""
        from agents.tools.sports_news import SportsNewsTool

        tool = SportsNewsTool()
        assert "calls" in tool.telemetry
        assert "errors" in tool.telemetry
        assert tool.telemetry["calls"] == 0


class TestWebpageSummarizerTool:
    """Tests for WebpageSummarizerTool (#109)."""

    def test_tool_instantiation(self):
        """Tool should instantiate without errors."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        assert tool.name == "summarize_webpage"
        assert tool.max_content_length == 30000  # Default
        assert tool.timeout == 20  # Default

    def test_tool_with_custom_params(self):
        """Tool should accept custom parameters."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool(max_content_length=10000, timeout=30)
        assert tool.max_content_length == 10000
        assert tool.timeout == 30

    def test_telemetry_initialized(self):
        """Tool should initialize telemetry dict with pages_summarized."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        assert "calls" in tool.telemetry
        assert "errors" in tool.telemetry
        assert "pages_summarized" in tool.telemetry
        assert tool.telemetry["pages_summarized"] == 0

    def test_invalid_url_returns_error(self):
        """Tool should return error for invalid URLs."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        result = tool.forward("not-a-valid-url")
        assert "Error" in result
        assert "Invalid URL" in result

    def test_empty_url_returns_error(self):
        """Tool should return error for empty URL."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        result = tool.forward("")
        assert "Error" in result
        assert "No URL" in result

    def test_truncate_content_under_limit(self):
        """Content under limit should not be truncated."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        content = "Short content"
        result = tool._truncate_content(content, 1000)
        assert result == content
        assert "[Content truncated" not in result

    def test_truncate_content_over_limit(self):
        """Content over limit should be truncated with marker."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        content = "a" * 200
        result = tool._truncate_content(content, 100)
        assert len(result) < 200
        assert "[Content truncated" in result

    def test_clean_markdown_removes_extra_newlines(self):
        """Clean markdown should reduce excessive newlines."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        content = "Line 1\n\n\n\n\nLine 2"
        result = tool._clean_markdown(content)
        assert "\n\n\n" not in result

    def test_extract_title_from_html(self):
        """Should extract title from HTML."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        html = "<html><head><title>Test Page Title</title></head></html>"
        title = tool._extract_title(html)
        assert title == "Test Page Title"

    def test_extract_title_missing(self):
        """Should return None when no title tag."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()
        html = "<html><head></head><body>Content</body></html>"
        title = tool._extract_title(html)
        assert title is None

    def test_creates_markdown_artifact(self):
        """Tool should create markdown artifact on successful summarization."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool
        from agents.tools.output_collections import InMemoryArtifactCollection

        collection = InMemoryArtifactCollection()
        tool = WebpageSummarizerTool(output_collection=collection)

        # Mock the fetch and summarize methods (content must be > 100 chars)
        long_content = "# Test Content\n\n" + "This is a test paragraph with enough content to pass the minimum length validation. " * 3
        with patch.object(tool, '_fetch_webpage') as mock_fetch, \
             patch.object(tool, '_summarize_content') as mock_summarize:
            mock_fetch.return_value = (long_content, "Test Page", None)
            mock_summarize.return_value = ("This is a summary of the test content.", None)

            result = tool.forward("https://example.com/article")

        # Verify artifact was created
        assert len(collection.artifacts) == 1
        artifact = collection.artifacts[0]
        assert artifact.type == "markdown"
        assert artifact.mime_type == "text/markdown"
        assert "Summary" in artifact.title

        # Verify result contains the summary
        assert "summary" in result.lower()
        assert "https://example.com/article" in result

    def test_fetch_error_returns_message(self):
        """Tool should return error message when fetch fails."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()

        with patch.object(tool, '_fetch_webpage') as mock_fetch:
            mock_fetch.return_value = ("", None, "Error: HTTP 404 from https://example.com")

            result = tool.forward("https://example.com/missing")

        assert "Error" in result
        assert "404" in result

    def test_summarize_error_returns_message(self):
        """Tool should return error message when summarization fails."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool

        tool = WebpageSummarizerTool()

        with patch.object(tool, '_fetch_webpage') as mock_fetch, \
             patch.object(tool, '_summarize_content') as mock_summarize:
            mock_fetch.return_value = ("Content here" * 50, "Test Page", None)
            mock_summarize.return_value = ("", "Error generating summary: API timeout")

            result = tool.forward("https://example.com/article")

        assert "Error" in result
        assert "summary" in result.lower() or "API" in result

    def test_focus_parameter_passed_to_summarization(self):
        """Focus parameter should be passed to the summarization step."""
        from agents.tools.webpage_summarizer import WebpageSummarizerTool
        from agents.tools.output_collections import InMemoryArtifactCollection

        collection = InMemoryArtifactCollection()
        tool = WebpageSummarizerTool(output_collection=collection)

        with patch.object(tool, '_fetch_webpage') as mock_fetch, \
             patch.object(tool, '_summarize_content') as mock_summarize:
            mock_fetch.return_value = ("Content here" * 50, "Test Page", None)
            mock_summarize.return_value = ("Technical summary focusing on API details.", None)

            tool.forward("https://example.com/api-docs", focus="technical details")

        # Verify focus was passed to summarize method
        mock_summarize.assert_called_once()
        call_args = mock_summarize.call_args
        assert call_args[1].get('focus') == "technical details" or call_args[0][1] == "technical details"


class TestImageGenerationTools:
    """Tests for image generation tools."""

    def test_openai_tool_instantiation(self):
        """OpenAI tool should instantiate."""
        from agents.tools.image_gen_openai import OpenAIImageGenTool

        with patch("agents.tools.image_gen_openai.OpenAI"):
            tool = OpenAIImageGenTool()
            assert tool.name == "image_gen_openai"
            assert tool._model_name == "gpt-image-1"

    def test_huggingface_tool_instantiation(self):
        """HuggingFace tool should instantiate."""
        from agents.tools.image_gen_hf import HuggingFaceImageGenTool

        tool = HuggingFaceImageGenTool()
        assert tool.name == "image_gen_huggingface"
        assert tool.default_model == "stabilityai/stable-diffusion-xl-base-1.0"

    def test_gemini_tool_instantiation(self):
        """Gemini tool should instantiate."""
        from agents.tools.image_gen_gemini import GeminiImageGenTool

        tool = GeminiImageGenTool()
        assert tool.name == "image_gen_gemini"
        assert tool._model_name == "gemini-2.0-flash-exp"

    def test_nano_banana_alias(self):
        """NanoBananaTool should be alias for GeminiImageGenTool."""
        from agents.tools.image_gen_gemini import GeminiImageGenTool, NanoBananaTool

        assert NanoBananaTool is GeminiImageGenTool


class TestUnstructuredTool:
    """Tests for UnstructuredTool."""

    def test_tool_instantiation(self):
        """Tool should instantiate."""
        from agents.tools.unstructured import UnstructuredTool

        tool = UnstructuredTool()
        assert tool.name == "unstructured_extract"

    def test_valid_strategies(self):
        """Tool should validate strategies."""
        from agents.tools.unstructured import UnstructuredTool

        tool = UnstructuredTool(api_key="test")
        assert "auto" in tool.VALID_STRATEGIES
        assert "hi_res" in tool.VALID_STRATEGIES

    def test_supported_extensions(self):
        """Tool should support common document formats."""
        from agents.tools.unstructured import UnstructuredTool

        tool = UnstructuredTool()
        assert ".pdf" in tool.SUPPORTED_EXTENSIONS
        assert ".docx" in tool.SUPPORTED_EXTENSIONS
        assert ".png" in tool.SUPPORTED_EXTENSIONS


class TestDocumentTools:
    """Tests for document processing tools."""

    def test_doc_tool_requires_store_id(self):
        """Document tool should require store_id parameter."""
        from agents.tools.document_retriever import DocumentRetrieverTool

        with patch("agents.tools.document_retriever.FileSearchRegistry"):
            tool = DocumentRetrieverTool(store_id="test-store-123")
            assert tool.store_id == "test-store-123"


class TestImageAnalyzerTool:
    """Tests for ImageAnalyzerTool."""

    def test_tool_instantiation(self):
        """Tool should instantiate."""
        from agents.tools.image_analyzer import ImageAnalyzerTool

        with patch("agents.tools.image_analyzer.OpenAI"):
            tool = ImageAnalyzerTool()
            assert tool.name == "image_analyzer"
            assert tool.model == "gpt-4o"


@pytest.mark.django_db
class TestProjectToolConfig:
    """Tests for ProjectToolConfig model."""

    def test_tool_config_creation(self, organization, project, user):
        """Should create tool config for project."""
        config = ProjectToolConfig.objects.create(
            organization=organization,
            project=project,
            tool_name="web_search",
            is_enabled=False,
            created_by=user,
        )
        assert config.tool_name == "web_search"
        assert config.is_enabled is False

    def test_unique_constraint(self, organization, project, user):
        """Should enforce unique project+tool_name."""
        ProjectToolConfig.objects.create(
            organization=organization,
            project=project,
            tool_name="web_search",
            created_by=user,
        )
        with pytest.raises(Exception):  # IntegrityError
            ProjectToolConfig.objects.create(
                organization=organization,
                project=project,
                tool_name="web_search",
                created_by=user,
            )


@pytest.fixture
def organization():
    """Create test organization."""
    from organizations.models import Organization

    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def project(organization):
    """Create test project."""
    from projects.models import Project

    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/tmp/test",
    )


@pytest.fixture
def user():
    """Create test user."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_user(username="testuser", password="testpass")


class TestArtifactOutputSchema:
    """Tests for artifact output schema and helper functions."""

    def test_artifact_schema_structure(self):
        """Schema should have required properties."""
        assert "properties" in ARTIFACT_OUTPUT_SCHEMA
        assert "result" in ARTIFACT_OUTPUT_SCHEMA["properties"]
        assert "artifacts" in ARTIFACT_OUTPUT_SCHEMA["properties"]

    def test_create_artifact_output_result_only(self):
        """Should create valid JSON with just result."""
        output = create_artifact_output(result="Operation completed")
        data = json.loads(output)

        assert data["result"] == "Operation completed"
        assert "artifacts" not in data

    def test_create_artifact_output_with_artifacts(self):
        """Should create valid JSON with artifacts."""
        output = create_artifact_output(
            result="Image generated",
            artifacts=[
                {
                    "type": "image",
                    "path": "/path/to/image.png",
                    "mime_type": "image/png",
                    "title": "Test Image",
                }
            ],
        )
        data = json.loads(output)

        assert data["result"] == "Image generated"
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["type"] == "image"
        assert data["artifacts"][0]["path"] == "/path/to/image.png"

    def test_extract_artifacts_plain_text(self):
        """Should return original text when not JSON."""
        result, artifacts = extract_artifacts_from_output("Plain text response")

        assert result == "Plain text response"
        assert artifacts == []

    def test_extract_artifacts_valid_json(self):
        """Should extract artifacts from valid JSON."""
        json_str = json.dumps({
            "result": "Success",
            "artifacts": [
                {"type": "image", "path": "/test.png"}
            ]
        })
        result, artifacts = extract_artifacts_from_output(json_str)

        assert result == "Success"
        assert len(artifacts) == 1
        assert artifacts[0]["type"] == "image"

    def test_extract_artifacts_json_no_artifacts(self):
        """Should handle JSON with no artifacts key."""
        json_str = json.dumps({"result": "Success"})
        result, artifacts = extract_artifacts_from_output(json_str)

        assert result == "Success"
        assert artifacts == []

    def test_extract_artifacts_empty_string(self):
        """Should handle empty string."""
        result, artifacts = extract_artifacts_from_output("")

        assert result == ""
        assert artifacts == []

    def test_extract_artifacts_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        result, artifacts = extract_artifacts_from_output("{invalid json")

        assert result == "{invalid json"
        assert artifacts == []


class TestImageGenToolsArtifactOutput:
    """Tests for image generation tools returning structured artifact output."""

    def test_gemini_tool_output_type(self):
        """Gemini tool should have string output_type (uses ZoeaTool artifact creation)."""
        from agents.tools.image_gen_gemini import GeminiImageGenTool

        tool = GeminiImageGenTool()
        # GeminiImageGenTool now extends ZoeaTool and returns plain strings
        # Artifacts are created directly via create_artifact() method
        assert tool.output_type == "string"

    def test_openai_tool_output_type(self):
        """OpenAI tool should have string output_type (ZoeaTool pattern)."""
        from agents.tools.image_gen_openai import OpenAIImageGenTool

        with patch("agents.tools.image_gen_openai.OpenAI"):
            tool = OpenAIImageGenTool()
            # OpenAIImageGenTool now extends ZoeaTool and returns plain strings
            # Artifacts are created directly via create_artifact() method
            assert tool.output_type == "string"

    def test_huggingface_tool_output_type(self):
        """HuggingFace tool should have string output_type (ZoeaTool pattern)."""
        from agents.tools.image_gen_hf import HuggingFaceImageGenTool

        tool = HuggingFaceImageGenTool()
        # HuggingFaceImageGenTool now extends ZoeaTool and returns plain strings
        # Artifacts are created directly via create_artifact() method
        assert tool.output_type == "string"

    def test_gemini_error_returns_plain_string(self):
        """Gemini tool errors should return plain string (ZoeaTool pattern)."""
        from agents.tools.image_gen_gemini import GeminiImageGenTool

        tool = GeminiImageGenTool()
        # Test with invalid aspect ratio
        output = tool.forward(prompt="test", aspect_ratio="invalid")

        # GeminiImageGenTool now returns plain strings (not JSON)
        assert isinstance(output, str)
        assert "Error" in output
        assert "invalid" in output.lower()

    def test_huggingface_error_returns_plain_string(self):
        """HuggingFace tool errors should return plain string (ZoeaTool pattern)."""
        from unittest.mock import patch

        import httpx

        from agents.tools.image_gen_hf import HuggingFaceImageGenTool

        tool = HuggingFaceImageGenTool()

        # Mock the HTTP request to raise an error
        with patch("httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Server error"
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=mock_response,
                )
            )

            output = tool.forward(prompt="test")

        # HuggingFaceImageGenTool now returns plain strings (not JSON)
        assert isinstance(output, str)
        assert "Error" in output
