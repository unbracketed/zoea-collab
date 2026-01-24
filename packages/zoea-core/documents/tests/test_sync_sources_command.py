"""
Tests for sync_sources management command.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from organizations.models import Organization

from projects.models import Project
from sources.models import Source
from sources.base import DocumentMetadata


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
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        test_dir = Path(tmpdir)
        (test_dir / "test.md").write_text("# Test Content")
        (test_dir / "test.csv").write_text("col1,col2\nval1,val2")
        (test_dir / "test.d2").write_text("shape: rectangle")
        yield tmpdir


@pytest.fixture
def source(db, project, temp_dir):
    """Create a test local filesystem source."""
    return Source.objects.create(
        project=project,
        organization=project.organization,
        source_type='local',
        name='Test Source',
        config={'path': temp_dir}
    )


@pytest.mark.django_db
class TestSyncSourcesCommand:
    """Test suite for sync_sources management command."""

    def test_no_sources(self):
        """Test command fails gracefully when no sources exist."""
        out = StringIO()

        with pytest.raises(CommandError, match="No sources found"):
            call_command('sync_sources', stdout=out)

    def test_sync_specific_source_by_name(self, source):
        """Test syncing a specific source by name."""
        out = StringIO()

        call_command('sync_sources', '--source', 'Test Source', stdout=out)

        output = out.getvalue()
        assert 'Test Source' in output
        assert 'local' in output.lower()

    def test_sync_specific_source_by_id(self, source):
        """Test syncing a specific source by ID."""
        out = StringIO()

        call_command('sync_sources', '--source', str(source.id), stdout=out)

        output = out.getvalue()
        assert 'Test Source' in output

    def test_sync_sources_for_project(self, source):
        """Test syncing all sources for a specific project."""
        out = StringIO()

        call_command('sync_sources', '--project', 'Test Project', stdout=out)

        output = out.getvalue()
        assert 'Test Project' in output
        assert 'Test Source' in output

    def test_sync_sources_for_project_by_id(self, project, source):
        """Test syncing sources for project by ID."""
        out = StringIO()

        call_command('sync_sources', '--project', str(project.id), stdout=out)

        output = out.getvalue()
        assert 'Test Project' in output

    def test_sync_sources_for_organization(self, organization, source):
        """Test syncing all sources in an organization."""
        out = StringIO()

        call_command('sync_sources', '--organization', 'Test Organization', stdout=out)

        output = out.getvalue()
        assert 'Test Organization' in output

    def test_sync_sources_for_organization_by_id(self, organization, source):
        """Test syncing sources for organization by ID."""
        out = StringIO()

        call_command('sync_sources', '--organization', str(organization.id), stdout=out)

        output = out.getvalue()
        assert 'Test Organization' in output

    def test_dry_run_mode(self, source):
        """Test dry run mode doesn't create documents."""
        from documents.models import Document

        initial_count = Document.objects.count()

        out = StringIO()
        call_command('sync_sources', '--source', 'Test Source', '--dry-run', stdout=out)

        output = out.getvalue()
        assert '[DRY RUN]' in output
        assert Document.objects.count() == initial_count

    def test_sync_creates_documents(self, source):
        """Test that sync creates document records."""
        from documents.models import Document

        initial_count = Document.objects.count()

        out = StringIO()
        call_command('sync_sources', '--source', 'Test Source', stdout=out)

        # Should have created 3 documents (test.md, test.csv, test.d2)
        assert Document.objects.count() > initial_count

    def test_sync_updates_source_timestamp(self, source):
        """Test that successful sync updates source.last_sync_at."""
        assert source.last_sync_at is None

        out = StringIO()
        call_command('sync_sources', '--source', 'Test Source', stdout=out)

        source.refresh_from_db()
        assert source.last_sync_at is not None

    def test_invalid_source_name(self):
        """Test error handling for invalid source name."""
        out = StringIO()

        with pytest.raises(CommandError, match="Source .* not found"):
            call_command('sync_sources', '--source', 'Nonexistent Source', stdout=out)

    def test_invalid_project_name(self):
        """Test error handling for invalid project name."""
        out = StringIO()

        with pytest.raises(CommandError, match="Project .* not found"):
            call_command('sync_sources', '--project', 'Nonexistent Project', stdout=out)

    def test_invalid_organization_name(self):
        """Test error handling for invalid organization name."""
        out = StringIO()

        with pytest.raises(CommandError, match="Organization .* not found"):
            call_command('sync_sources', '--organization', 'Nonexistent Org', stdout=out)

    def test_inactive_source_not_synced(self, source):
        """Test that inactive sources are not synced when using --all."""
        source.is_active = False
        source.save()

        out = StringIO()

        with pytest.raises(CommandError, match="No sources found"):
            call_command('sync_sources', '--all', stdout=out)

    @patch('documents.management.commands.sync_sources.Command.sync_document')
    def test_failed_document_sync_continues(self, mock_sync, source):
        """Test that sync continues even if individual documents fail."""
        # Make sync_document raise an exception
        mock_sync.side_effect = Exception("Test error")

        out = StringIO()
        call_command('sync_sources', '--source', 'Test Source', stdout=out)

        output = out.getvalue()
        assert '✗ Failed' in output
        # Should show that it tried to sync and failed
        assert mock_sync.call_count > 0

    def test_sync_skips_unchanged_documents(self, source):
        """Test that sync skips documents that haven't changed."""
        from documents.models import Document

        # First sync
        out1 = StringIO()
        call_command('sync_sources', '--source', 'Test Source', stdout=out1)

        initial_count = Document.objects.count()

        # Second sync (should skip unchanged)
        out2 = StringIO()
        call_command('sync_sources', '--source', 'Test Source', stdout=out2)

        output = out2.getvalue()
        # Documents should be skipped
        assert 'Skipped' in output or 'unchanged' in output.lower()
        # Count should remain the same
        assert Document.objects.count() == initial_count
