"""
Tests for query_gemini_store management command.
"""

from io import StringIO
from unittest.mock import Mock, patch, MagicMock

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
    """Create a test project with File Search store."""
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
    with patch('documents.management.commands.query_gemini_store.GeminiFileSearchService') as mock:
        service_instance = Mock()
        mock.return_value = service_instance
        yield service_instance


@pytest.fixture
def mock_response():
    """Create a mock Gemini response."""
    response = Mock()
    response.text = "This is a test response from the File Search query."

    # Mock candidate with grounding metadata
    candidate = Mock()
    grounding = Mock()

    # Mock grounding chunk
    chunk = Mock()
    context = Mock()
    context.title = "Test Document"
    context.uri = "files/test-file-123"
    context.text = "This is the relevant text from the document that answers the query."
    chunk.retrieved_context = context

    grounding.grounding_chunks = [chunk]
    grounding.grounding_supports = []

    candidate.grounding_metadata = grounding
    response.candidates = [candidate]

    return response


@pytest.mark.django_db
class TestQueryGeminiStoreCommand:
    """Test suite for query_gemini_store management command."""

    def test_query_by_project_name(self, project, mock_gemini_service, mock_response):
        """Test querying by project name."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'What is the project about?',
            '--project', 'Test Project',
            stdout=out
        )

        output = out.getvalue()
        assert 'Test Project' in output
        assert 'This is a test response' in output

        # Verify generate_content was called
        mock_gemini_service.client.models.generate_content.assert_called_once()

    def test_query_by_project_id(self, project, mock_gemini_service, mock_response):
        """Test querying by project ID."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'What is the project about?',
            '--project', str(project.id),
            stdout=out
        )

        output = out.getvalue()
        assert 'Test Project' in output

        # Verify generate_content was called
        mock_gemini_service.client.models.generate_content.assert_called_once()

    def test_query_by_store_id(self, mock_gemini_service, mock_response):
        """Test querying by store ID directly."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'What documents are in this store?',
            '--store-id', 'fileSearchStores/test-store-123',
            stdout=out
        )

        output = out.getvalue()
        assert 'fileSearchStores/test-store-123' in output

        # Verify generate_content was called with correct store ID
        call_args = mock_gemini_service.client.models.generate_content.call_args
        assert 'fileSearchStores/test-store-123' in str(call_args)

    def test_query_nonexistent_project(self, mock_gemini_service):
        """Test querying nonexistent project fails."""
        with pytest.raises(CommandError, match="Project .* not found"):
            call_command(
                'query_gemini_store',
                'Test query',
                '--project', 'Nonexistent Project'
            )

    def test_query_project_without_store(self, organization, django_user_model, mock_gemini_service):
        """Test querying project without File Search store fails."""
        user = django_user_model.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123"
        )
        project_no_store = Project.objects.create(
            organization=organization,
            name="Project Without Store",
            working_directory="/test/path2",
            created_by=user
        )

        with pytest.raises(CommandError, match="does not have a File Search store"):
            call_command(
                'query_gemini_store',
                'Test query',
                '--project', 'Project Without Store'
            )

    def test_query_without_project_or_store_id(self, mock_gemini_service):
        """Test command fails without project or store ID."""
        with pytest.raises(CommandError, match="Either --project or --store-id must be specified"):
            call_command('query_gemini_store', 'Test query')

    def test_query_with_metadata_filter(self, project, mock_gemini_service, mock_response):
        """Test querying with metadata filter."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Find markdown documents',
            '--project', 'Test Project',
            '--metadata-filter', 'document_type=Markdown',
            stdout=out
        )

        output = out.getvalue()
        assert 'Metadata Filter: document_type=Markdown' in output

        # Verify metadata filter was included in API call
        call_args = mock_gemini_service.client.models.generate_content.call_args
        assert 'document_type=Markdown' in str(call_args)

    def test_query_with_custom_model(self, project, mock_gemini_service, mock_response):
        """Test querying with custom model."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            '--model', 'gemini-2.0-flash',
            stdout=out
        )

        output = out.getvalue()
        assert 'Model: gemini-2.0-flash' in output

        # Verify custom model was used in API call
        call_args = mock_gemini_service.client.models.generate_content.call_args
        assert call_args[1]['model'] == 'gemini-2.0-flash'

    def test_query_show_citations(self, project, mock_gemini_service, mock_response):
        """Test showing citations in output."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            '--show-citations',
            stdout=out
        )

        output = out.getvalue()
        assert 'Citations:' in output
        assert 'Test Document' in output
        assert 'files/test-file-123' in output

    def test_query_verbose_mode(self, project, mock_gemini_service, mock_response):
        """Test verbose output mode."""
        mock_gemini_service.client.models.generate_content.return_value = mock_response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            '--verbose',
            stdout=out
        )

        output = out.getvalue()
        assert 'Citations:' in output
        assert 'Grounding Metadata (Verbose):' in output

    def test_query_response_without_text(self, project, mock_gemini_service):
        """Test handling response without text."""
        response = Mock()
        response.text = None
        response.candidates = []

        mock_gemini_service.client.models.generate_content.return_value = response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            stdout=out
        )

        output = out.getvalue()
        assert 'No text response generated' in output

    def test_query_response_without_grounding(self, project, mock_gemini_service):
        """Test handling response without grounding metadata."""
        response = Mock()
        response.text = "Response without grounding"
        response.candidates = []

        mock_gemini_service.client.models.generate_content.return_value = response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            '--show-citations',
            stdout=out
        )

        output = out.getvalue()
        assert 'No candidates in response' in output

    def test_query_api_error(self, project, mock_gemini_service):
        """Test handling API errors."""
        mock_gemini_service.client.models.generate_content.side_effect = Exception("API error")

        with pytest.raises(CommandError, match="Query failed"):
            call_command(
                'query_gemini_store',
                'Test query',
                '--project', 'Test Project'
            )

    def test_missing_api_key_error(self, project):
        """Test command fails without API key."""
        with patch('documents.management.commands.query_gemini_store.GeminiFileSearchService') as mock:
            mock.side_effect = ValueError("GEMINI_API_KEY not found in settings")

            with pytest.raises(CommandError, match="GEMINI_API_KEY"):
                call_command(
                    'query_gemini_store',
                    'Test query',
                    '--project', 'Test Project'
                )

    def test_query_with_long_response(self, project, mock_gemini_service):
        """Test word wrapping for long responses."""
        response = Mock()
        response.text = "This is a very long response " * 50  # Long text
        response.candidates = []

        mock_gemini_service.client.models.generate_content.return_value = response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            stdout=out
        )

        output = out.getvalue()
        # Check that text is present and wrapped (lines should not be too long)
        lines = output.split('\n')
        for line in lines:
            assert len(line) <= 80  # Reasonable line length

    def test_query_with_multiple_grounding_chunks(self, project, mock_gemini_service):
        """Test displaying multiple citation sources."""
        response = Mock()
        response.text = "Response using multiple sources"

        # Create multiple grounding chunks
        chunk1 = Mock()
        context1 = Mock()
        context1.title = "Document 1"
        context1.uri = "files/file1"
        context1.text = "Text from first document"
        chunk1.retrieved_context = context1

        chunk2 = Mock()
        context2 = Mock()
        context2.title = "Document 2"
        context2.uri = "files/file2"
        context2.text = "Text from second document"
        chunk2.retrieved_context = context2

        candidate = Mock()
        grounding = Mock()
        grounding.grounding_chunks = [chunk1, chunk2]
        grounding.grounding_supports = []
        candidate.grounding_metadata = grounding
        response.candidates = [candidate]

        mock_gemini_service.client.models.generate_content.return_value = response

        out = StringIO()
        call_command(
            'query_gemini_store',
            'Test query',
            '--project', 'Test Project',
            '--show-citations',
            stdout=out
        )

        output = out.getvalue()
        assert 'Found 2 source(s)' in output
        assert 'Document 1' in output
        assert 'Document 2' in output
