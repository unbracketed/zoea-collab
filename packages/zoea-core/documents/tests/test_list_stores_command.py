"""
Tests for list_gemini_stores management command.
"""

from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from organizations.models import Organization

from projects.models import Project


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(
        name="Test Organization",
        slug="test-org"
    )


@pytest.fixture
def project(db, organization, django_user_model):
    """Create a test project."""
    user = django_user_model.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    return Project.objects.create(
        organization=organization,
        name="Test Project",
        working_directory="/test/path",
        created_by=user,
        gemini_store_id="fileSearchStores/test-store-123",
        gemini_store_name="Test Store",
        gemini_synced_at=timezone.now()
    )


@pytest.fixture
def mock_gemini_service():
    """Mock GeminiFileSearchService."""
    with patch('documents.management.commands.list_gemini_stores.GeminiFileSearchService') as mock:
        service_instance = Mock()
        mock.return_value = service_instance
        yield service_instance


@pytest.mark.django_db
class TestListGeminiStoresCommand:
    """Test suite for list_gemini_stores management command."""

    def test_no_stores(self, mock_gemini_service):
        """Test command when no stores exist."""
        mock_gemini_service.list_stores.return_value = []

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'No File Search stores found' in output

    def test_list_stores_with_matched_project(self, project, mock_gemini_service):
        """Test listing stores that match projects."""
        # Mock store that matches the project
        mock_store = Mock()
        mock_store.name = "fileSearchStores/test-store-123"
        mock_store.display_name = "Test Store"

        mock_gemini_service.list_stores.return_value = [mock_store]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'Found 1 store(s)' in output
        assert 'Test Project' in output
        assert 'Test Organization' in output
        assert 'fileSearchStores/test-store-123' in output

    def test_list_stores_with_unmatched_store(self, mock_gemini_service):
        """Test listing stores that don't match any project."""
        # Mock store that doesn't match any project
        mock_store = Mock()
        mock_store.name = "fileSearchStores/orphaned-store-456"
        mock_store.display_name = "Orphaned Store"

        mock_gemini_service.list_stores.return_value = [mock_store]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'Found 1 store(s)' in output
        assert 'Not matched to any project' in output
        assert 'Unmatched (orphaned): 1' in output

    def test_list_stores_verbose(self, project, mock_gemini_service):
        """Test verbose output mode."""
        # Mock store with additional attributes
        mock_store = Mock()
        mock_store.name = "fileSearchStores/test-store-123"
        mock_store.display_name = "Test Store"
        mock_store.create_time = "2024-01-01T00:00:00Z"
        mock_store.update_time = "2024-01-02T00:00:00Z"

        mock_gemini_service.list_stores.return_value = [mock_store]

        out = StringIO()
        call_command('list_gemini_stores', '--verbose', stdout=out)

        output = out.getvalue()
        assert 'Additional Details:' in output
        assert 'Created:' in output
        assert 'Updated:' in output

    def test_list_multiple_stores(self, project, mock_gemini_service):
        """Test listing multiple stores."""
        # Create second project
        project2 = Project.objects.create(
            organization=project.organization,
            name="Second Project",
            working_directory="/test/path2",
            created_by=project.created_by,
            gemini_store_id="fileSearchStores/test-store-456",
            gemini_store_name="Second Store"
        )

        # Mock multiple stores
        mock_store1 = Mock()
        mock_store1.name = "fileSearchStores/test-store-123"
        mock_store1.display_name = "Test Store"

        mock_store2 = Mock()
        mock_store2.name = "fileSearchStores/test-store-456"
        mock_store2.display_name = "Second Store"

        mock_gemini_service.list_stores.return_value = [mock_store1, mock_store2]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'Found 2 store(s)' in output
        assert 'Test Project' in output
        assert 'Second Project' in output
        assert 'Total stores: 2' in output
        assert 'Matched to projects: 2' in output

    def test_list_stores_mixed_matched_unmatched(self, project, mock_gemini_service):
        """Test listing stores with both matched and unmatched stores."""
        # Mock matched and unmatched stores
        mock_store1 = Mock()
        mock_store1.name = "fileSearchStores/test-store-123"
        mock_store1.display_name = "Test Store"

        mock_store2 = Mock()
        mock_store2.name = "fileSearchStores/orphaned-store"
        mock_store2.display_name = "Orphaned Store"

        mock_gemini_service.list_stores.return_value = [mock_store1, mock_store2]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'Found 2 store(s)' in output
        assert 'Total stores: 2' in output
        assert 'Matched to projects: 1' in output
        assert 'Unmatched (orphaned): 1' in output
        assert 'Test Project' in output
        assert 'Not matched to any project' in output

    def test_service_initialization_error(self):
        """Test command fails gracefully without API key."""
        with patch('documents.management.commands.list_gemini_stores.GeminiFileSearchService') as mock:
            mock.side_effect = ValueError("GEMINI_API_KEY not found in settings")

            with pytest.raises(CommandError, match="GEMINI_API_KEY"):
                call_command('list_gemini_stores')

    def test_list_stores_api_error(self, mock_gemini_service):
        """Test command handles API errors gracefully."""
        mock_gemini_service.list_stores.side_effect = Exception("API connection failed")

        with pytest.raises(CommandError, match="Failed to list stores"):
            call_command('list_gemini_stores')

    def test_display_last_synced_time(self, project, mock_gemini_service):
        """Test command displays last synced timestamp."""
        mock_store = Mock()
        mock_store.name = "fileSearchStores/test-store-123"
        mock_store.display_name = "Test Store"

        mock_gemini_service.list_stores.return_value = [mock_store]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'Last Synced:' in output

    def test_cleanup_suggestion_for_orphans(self, mock_gemini_service):
        """Test command suggests cleanup for orphaned stores."""
        mock_store = Mock()
        mock_store.name = "fileSearchStores/orphaned-store"
        mock_store.display_name = "Orphaned Store"

        mock_gemini_service.list_stores.return_value = [mock_store]

        out = StringIO()
        call_command('list_gemini_stores', stdout=out)

        output = out.getvalue()
        assert 'sync_gemini_file_search --delete-store' in output
        assert 'Orphaned stores may have been created for deleted projects' in output
