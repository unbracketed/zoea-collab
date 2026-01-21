"""
Tests for sync_gemini_file_search management command.
"""

from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from organizations.models import Organization

from documents.models import Markdown
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
        created_by=user
    )


@pytest.fixture
def markdown_document(db, organization, project, django_user_model):
    """Create a test markdown document."""
    user = django_user_model.objects.get(username="testuser")
    return Markdown.objects.create(
        organization=organization,
        project=project,
        name="Test Document",
        content="# Test Content",
        created_by=user
    )


@pytest.fixture
def mock_file_search():
    """Mock file search store integrations."""
    with (
        patch('documents.management.commands.sync_gemini_file_search.FileSearchRegistry') as registry_cls,
        patch('documents.management.commands.sync_gemini_file_search.ensure_project_store') as ensure_store,
        patch('documents.management.commands.sync_gemini_file_search.index_document') as index_document,
    ):
        store_instance = Mock()
        registry_cls.get.return_value = store_instance
        store_info = Mock()
        store_info.store_id = 'fileSearchStores/test-store'
        store_info.display_name = 'Test Store'
        ensure_store.return_value = store_info
        yield store_instance, ensure_store, index_document


@pytest.mark.django_db
class TestSyncGeminiFileSearchCommand:
    """Test suite for sync_gemini_file_search management command."""

    def test_no_projects(self, mock_file_search):
        """Test command fails gracefully when no projects exist."""
        out = StringIO()

        with pytest.raises(CommandError, match="No projects found"):
            call_command('sync_gemini_file_search', stdout=out)

    def test_sync_specific_project_by_name(self, project, markdown_document, mock_file_search):
        """Test syncing a specific project by name."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--project', 'Test Project', stdout=out)

        output = out.getvalue()
        assert 'Test Project' in output
        assert '✓' in output  # Success indicator

        # Verify indexing helpers were called
        _, ensure_store, index_document = mock_file_search
        ensure_store.assert_called_once()
        index_document.assert_called_once()

    def test_sync_specific_project_by_id(self, project, markdown_document, mock_file_search):
        """Test syncing a specific project by ID."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--project', str(project.id), stdout=out)

        output = out.getvalue()
        assert 'Test Project' in output

        # Verify indexing helpers were called
        _, ensure_store, _ = mock_file_search
        ensure_store.assert_called_once()

    def test_sync_nonexistent_project(self, mock_file_search):
        """Test command fails for nonexistent project."""
        with pytest.raises(CommandError, match="Project .* not found"):
            call_command('sync_gemini_file_search', '--project', 'Nonexistent Project')

    def test_sync_organization(self, organization, project, markdown_document, mock_file_search):
        """Test syncing all projects in an organization."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--organization', 'Test Organization', stdout=out)

        output = out.getvalue()
        assert 'Test Organization' in output
        assert 'Test Project' in output

        # Verify indexing helpers were called
        _, ensure_store, index_document = mock_file_search
        ensure_store.assert_called_once()
        index_document.assert_called_once()

    def test_sync_all_projects(self, project, markdown_document, mock_file_search):
        """Test syncing all projects."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--all', stdout=out)

        output = out.getvalue()
        assert 'Test Project' in output

        # Verify indexing helpers were called
        _, ensure_store, index_document = mock_file_search
        ensure_store.assert_called_once()
        index_document.assert_called_once()

    def test_dry_run_mode(self, project, markdown_document, mock_file_search):
        """Test dry-run mode doesn't actually sync."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--project', 'Test Project', '--dry-run', stdout=out)

        output = out.getvalue()
        assert '[DRY RUN]' in output
        assert 'Test Project' in output

        # Verify indexing helpers were not invoked in dry-run
        _, ensure_store, index_document = mock_file_search
        ensure_store.assert_not_called()
        index_document.assert_not_called()

    def test_force_resync(self, project, markdown_document, mock_file_search):
        """Test force flag re-syncs already synced documents."""
        # Mark document as already synced
        markdown_document.gemini_file_id = 'files/old-file'
        markdown_document.gemini_synced_at = '2024-01-01T00:00:00Z'
        markdown_document.save()

        out = StringIO()

        call_command('sync_gemini_file_search', '--project', 'Test Project', '--force', stdout=out)

        # Verify indexer was called despite document already being synced
        _, _, index_document = mock_file_search
        index_document.assert_called_once_with(markdown_document, force=True)

    def test_delete_store(self, project, mock_file_search):
        """Test deleting File Search store."""
        # Set store ID on project
        project.gemini_store_id = 'fileSearchStores/test-store'
        project.save()

        out = StringIO()

        call_command('sync_gemini_file_search', '--project', 'Test Project', '--delete-store', stdout=out)

        output = out.getvalue()
        assert 'Deleted' in output or 'delete' in output.lower()

        # Verify delete was called
        store_instance, _, _ = mock_file_search
        store_instance.delete_store.assert_called_once_with('fileSearchStores/test-store')

        # Verify project store ID was cleared
        project.refresh_from_db()
        assert project.gemini_store_id is None
        assert project.gemini_store_name is None

    def test_delete_store_dry_run(self, project, mock_file_search):
        """Test delete with dry-run doesn't actually delete."""
        # Set store ID on project
        project.gemini_store_id = 'fileSearchStores/test-store'
        project.save()

        out = StringIO()

        call_command(
            'sync_gemini_file_search',
            '--project', 'Test Project',
            '--delete-store',
            '--dry-run',
            stdout=out
        )

        output = out.getvalue()
        assert '[DRY RUN]' in output

        # Verify delete was NOT called
        store_instance, _, _ = mock_file_search
        store_instance.delete_store.assert_not_called()

        # Verify project store ID was NOT cleared
        project.refresh_from_db()
        assert project.gemini_store_id == 'fileSearchStores/test-store'

    def test_custom_chunking_config(self, project, markdown_document, mock_file_search):
        """Test custom chunking configuration is accepted."""
        out = StringIO()

        call_command(
            'sync_gemini_file_search',
            '--project', 'Test Project',
            '--max-tokens-per-chunk', '500',
            '--max-overlap-tokens', '50',
            stdout=out
        )

        # Verify indexing was still invoked
        _, _, index_document = mock_file_search
        index_document.assert_called_once()

    def test_no_documents_to_sync(self, project, mock_file_search):
        """Test command handles project with no documents."""
        out = StringIO()

        call_command('sync_gemini_file_search', '--project', 'Test Project', stdout=out)

        output = out.getvalue()
        assert 'No documents to sync' in output or 'Test Project' in output

        # Store should still be created even without documents
        _, ensure_store, _ = mock_file_search
        ensure_store.assert_called_once()

    def test_upload_failure_continues(self, project, markdown_document, mock_file_search):
        """Test command continues after upload failure."""
        # Mock indexing to raise exception
        _, _, index_document = mock_file_search
        index_document.side_effect = Exception("Upload failed")

        out = StringIO()

        # Command should not raise exception
        call_command('sync_gemini_file_search', '--project', 'Test Project', stdout=out)

        output = out.getvalue()
        assert '✗' in output or 'Failed' in output

    def test_missing_api_key_error(self, project, markdown_document):
        """Test command fails gracefully without API key."""
        with patch('documents.management.commands.sync_gemini_file_search.FileSearchRegistry') as registry_cls:
            registry_cls.get.side_effect = ValueError("FILE_SEARCH_BACKEND not configured")

            with pytest.raises(CommandError, match="FILE_SEARCH_BACKEND"):
                call_command('sync_gemini_file_search', '--project', 'Test Project')
