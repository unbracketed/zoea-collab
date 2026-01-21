"""
Tests for Gemini File Search service.

Tests both the legacy import path (documents.gemini_service.GeminiFileSearchService)
and the new location (file_search.backends.gemini.GeminiFileSearchStore).
"""

from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from organizations.models import Organization

from documents.gemini_service import GeminiFileSearchService
from documents.models import Markdown
from file_search.exceptions import StoreError
from projects.models import Project


@pytest.fixture
def mock_genai_client():
    """Mock genai.Client for testing."""
    with patch("file_search.backends.gemini.genai.Client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_gemini_settings():
    """Mock GEMINI_API_KEY setting for tests."""
    with patch.object(settings, "GEMINI_API_KEY", "test-api-key"):
        yield


@pytest.fixture
def gemini_service(mock_genai_client, mock_gemini_settings):
    """Create GeminiFileSearchService instance with mocked client."""
    service = GeminiFileSearchService()
    return service


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(name="Test Organization", slug="test-org")


@pytest.fixture
def project(db, organization, django_user_model):
    """Create a test project."""
    user = django_user_model.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/test/path",
        created_by=user,
    )


@pytest.fixture
def markdown_document(db, organization, project, django_user_model):
    """Create a test markdown document."""
    user = django_user_model.objects.get(username="testuser")
    return Markdown.objects.create(
        organization=organization,
        project=project,
        name="Test Document",
        content="# Test Content\n\nThis is a test document.",
        created_by=user,
    )


@pytest.mark.django_db
class TestGeminiFileSearchService:
    """Test suite for GeminiFileSearchService."""

    def test_initialization_with_api_key(self, mock_genai_client):
        """Test service initializes with API key from settings."""
        with patch.object(settings, "GEMINI_API_KEY", "test-api-key"):
            service = GeminiFileSearchService()
            assert service.client is not None
            mock_genai_client.assert_called_once_with(api_key="test-api-key")

    def test_initialization_without_api_key(self, mock_genai_client):
        """Test service raises error without API key."""
        with patch.object(settings, "GEMINI_API_KEY", None):
            with pytest.raises(StoreError, match="GEMINI_API_KEY not found"):
                GeminiFileSearchService()

    def test_create_new_store(self, gemini_service, project):
        """Test creating a new File Search store for a project."""
        # Mock the file_search_stores.create method
        mock_store = Mock()
        mock_store.name = "fileSearchStores/test-store-123"
        mock_store.display_name = f"{project.organization.name} - {project.name}"

        gemini_service.client.file_search_stores.create.return_value = mock_store

        result = gemini_service.create_or_get_store(project)

        # Verify store creation was called
        gemini_service.client.file_search_stores.create.assert_called_once()

        # Verify result
        assert result["name"] == "fileSearchStores/test-store-123"
        assert result["display_name"] == f"{project.organization.name} - {project.name}"

        # Verify project was updated
        project.refresh_from_db()
        assert project.gemini_store_id == "fileSearchStores/test-store-123"
        assert project.gemini_store_name == f"{project.organization.name} - {project.name}"

    def test_get_existing_store(self, gemini_service, project):
        """Test retrieving existing File Search store for a project."""
        # Set existing store ID on project
        project.gemini_store_id = "fileSearchStores/existing-store"
        project.gemini_store_name = "Existing Store"
        project.save()

        # Mock the file_search_stores.get method
        mock_store = Mock()
        mock_store.name = "fileSearchStores/existing-store"
        mock_store.display_name = "Existing Store"

        gemini_service.client.file_search_stores.get.return_value = mock_store

        result = gemini_service.create_or_get_store(project)

        # Verify get was called instead of create
        gemini_service.client.file_search_stores.get.assert_called_once_with(
            name="fileSearchStores/existing-store"
        )
        gemini_service.client.file_search_stores.create.assert_not_called()

        # Verify result
        assert result["name"] == "fileSearchStores/existing-store"
        assert result["display_name"] == "Existing Store"

    def test_upload_text_document(self, gemini_service, markdown_document):
        """Test uploading a text-based document."""
        store_id = "fileSearchStores/test-store"

        # Mock the upload operation
        mock_operation = Mock()
        mock_operation.done = True
        mock_operation.response = Mock()
        mock_operation.response.name = "files/uploaded-file-123"

        gemini_service.client.file_search_stores.upload_to_file_search_store.return_value = (
            mock_operation
        )

        result = gemini_service.upload_document(markdown_document, store_id)

        # Verify upload was called
        gemini_service.client.file_search_stores.upload_to_file_search_store.assert_called_once()

        # Verify file_id in result
        assert result["file_id"] == "files/uploaded-file-123"
        assert result["display_name"] == "Test Document"

    def test_get_document_content_markdown(self, gemini_service, markdown_document):
        """Test extracting content from markdown document."""
        content_info = gemini_service.get_document_content(markdown_document)

        assert content_info["type"] == "text"
        assert content_info["content"] == "# Test Content\n\nThis is a test document."

    def test_build_metadata(self, gemini_service, markdown_document):
        """Test building metadata for document in Gemini format."""
        # Use the Gemini-specific metadata builder
        metadata = gemini_service._build_gemini_metadata(markdown_document)

        # Convert to dict for easier assertion
        metadata_dict = {item["key"]: item for item in metadata}

        # Check required metadata
        assert "document_type" in metadata_dict
        assert metadata_dict["document_type"]["string_value"] == "Markdown"

        assert "organization_id" in metadata_dict
        assert (
            metadata_dict["organization_id"]["numeric_value"] == markdown_document.organization_id
        )

        assert "project_id" in metadata_dict
        assert metadata_dict["project_id"]["numeric_value"] == markdown_document.project_id

        assert "author" in metadata_dict
        assert metadata_dict["author"]["string_value"] == markdown_document.created_by.username

    def test_delete_store(self, gemini_service):
        """Test deleting a File Search store."""
        store_id = "fileSearchStores/test-store"

        gemini_service.delete_store(store_id)

        # Verify delete was called
        gemini_service.client.file_search_stores.delete.assert_called_once_with(
            name=store_id, config={"force": True}
        )

    def test_list_stores(self, gemini_service):
        """Test listing all File Search stores."""
        mock_store1 = Mock()
        mock_store1.name = "fileSearchStores/store-1"
        mock_store1.display_name = "Store 1"

        mock_store2 = Mock()
        mock_store2.name = "fileSearchStores/store-2"
        mock_store2.display_name = "Store 2"

        gemini_service.client.file_search_stores.list.return_value = [
            mock_store1,
            mock_store2,
        ]

        stores = list(gemini_service.list_stores())

        # Verify list was called
        gemini_service.client.file_search_stores.list.assert_called_once()

        # Verify we got StoreInfo objects back
        assert len(stores) == 2
        assert stores[0].store_id == "fileSearchStores/store-1"
        assert stores[0].display_name == "Store 1"
        assert stores[0].backend == "gemini"

    def test_upload_waits_for_completion(self, gemini_service, markdown_document):
        """Test upload waits for operation to complete."""
        store_id = "fileSearchStores/test-store"

        # Mock operations with done=False then done=True
        mock_operation_incomplete = Mock()
        mock_operation_incomplete.done = False

        mock_operation_complete = Mock()
        mock_operation_complete.done = True
        mock_operation_complete.response = Mock()
        mock_operation_complete.response.name = "files/uploaded-file-123"

        gemini_service.client.file_search_stores.upload_to_file_search_store.return_value = (
            mock_operation_incomplete
        )
        gemini_service.client.operations.get.return_value = mock_operation_complete

        with patch("file_search.backends.gemini.time.sleep"):  # Skip actual sleep
            result = gemini_service.upload_document(markdown_document, store_id)

        # Verify operations.get was called to check completion
        gemini_service.client.operations.get.assert_called_once_with(mock_operation_incomplete)
        assert result["file_id"] == "files/uploaded-file-123"
