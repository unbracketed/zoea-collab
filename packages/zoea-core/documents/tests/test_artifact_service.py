"""Tests for the artifact service."""

import pytest
from django.contrib.auth import get_user_model

from chat.models import Conversation
from documents.artifact_service import (
    ArtifactService,
    get_or_create_artifacts_for_conversation,
    get_or_create_artifacts_for_workflow_run,
)
from documents.models import (
    CollectionItemSourceChannel,
    CollectionType,
    Document,
    DocumentCollection,
    DocumentCollectionItem,
)
from execution.models import ExecutionRun

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass',
    )


@pytest.fixture
def organization(db):
    """Create a test organization."""
    from organizations.models import Organization
    return Organization.objects.create(name='Test Org')


@pytest.fixture
def project(db, organization, user):
    """Create a test project."""
    from projects.models import Project
    return Project.objects.create(
        organization=organization,
        name='Test Project',
        created_by=user,
    )


@pytest.fixture
def conversation(db, organization, project, user):
    """Create a test conversation."""
    return Conversation.objects.create(
        organization=organization,
        project=project,
        created_by=user,
        title='Test Conversation',
    )


@pytest.fixture
def workflow_run(db, organization, project, user):
    """Create a test workflow run."""
    return ExecutionRun.objects.create(
        organization=organization,
        project=project,
        created_by=user,
        workflow_slug='test-workflow',
    )


@pytest.fixture
def artifact_service(user):
    """Create an artifact service instance."""
    return ArtifactService(actor=user)


class TestArtifactService:
    """Tests for ArtifactService class."""

    def test_get_or_create_artifacts_creates_new_collection(
        self, artifact_service, conversation
    ):
        """Test that get_or_create_artifacts creates a new collection."""
        assert conversation.artifacts is None

        collection = artifact_service.get_or_create_artifacts(conversation)

        assert collection is not None
        assert collection.collection_type == CollectionType.ARTIFACT
        assert collection.organization == conversation.organization
        assert collection.project == conversation.project

        # Verify conversation was updated
        conversation.refresh_from_db()
        assert conversation.artifacts_id == collection.id

    def test_get_or_create_artifacts_returns_existing_collection(
        self, artifact_service, conversation, organization, project, user
    ):
        """Test that get_or_create_artifacts returns existing collection."""
        # Pre-create a collection
        existing = DocumentCollection.objects.create(
            organization=organization,
            project=project,
            collection_type=CollectionType.ARTIFACT,
            name='Existing',
            created_by=user,
        )
        conversation.artifacts = existing
        conversation.save()

        collection = artifact_service.get_or_create_artifacts(conversation)

        assert collection.id == existing.id

    def test_get_or_create_artifacts_with_custom_name(
        self, artifact_service, conversation
    ):
        """Test custom naming for artifact collections."""
        collection = artifact_service.get_or_create_artifacts(
            conversation,
            name='Custom Artifacts Name',
        )

        assert collection.name == 'Custom Artifacts Name'

    def test_get_or_create_artifacts_for_workflow_run(
        self, artifact_service, workflow_run
    ):
        """Test artifact creation for workflow runs."""
        collection = artifact_service.get_or_create_artifacts(workflow_run)

        assert collection is not None
        assert collection.collection_type == CollectionType.ARTIFACT
        assert collection.organization == workflow_run.organization

        workflow_run.refresh_from_db()
        assert workflow_run.artifacts_id == collection.id

    def test_add_artifact_with_content_object(
        self, artifact_service, conversation, organization, project, user
    ):
        """Test adding an artifact with a content object reference."""
        collection = artifact_service.get_or_create_artifacts(conversation)

        # Create a document to reference
        doc = Document.objects.create(
            organization=organization,
            project=project,
            created_by=user,
            name='Test Doc',
        )

        result = artifact_service.add_artifact(
            collection,
            content_object=doc,
            source_channel=CollectionItemSourceChannel.DOCUMENT,
            source_metadata={'document_type': 'markdown'},
        )

        assert result.item is not None
        assert result.item.content_object == doc
        assert result.item.source_channel == CollectionItemSourceChannel.DOCUMENT

    def test_add_artifact_without_content_object(
        self, artifact_service, conversation
    ):
        """Test adding a virtual artifact without a content object."""
        collection = artifact_service.get_or_create_artifacts(conversation)

        result = artifact_service.add_artifact(
            collection,
            source_channel=CollectionItemSourceChannel.CODE,
            source_metadata={'language': 'python', 'code': 'print("hello")'},
        )

        assert result.item is not None
        assert result.item.content_type is None
        assert result.item.source_metadata['language'] == 'python'

    def test_add_artifact_to_non_artifact_collection_fails(
        self, artifact_service, organization, project, user
    ):
        """Test that adding to non-artifact collection raises error."""
        notebook = DocumentCollection.objects.create(
            organization=organization,
            project=project,
            collection_type=CollectionType.NOTEBOOK,
            name='Test Notebook',
            owner=user,
            created_by=user,
        )

        with pytest.raises(ValueError, match='not an artifact collection'):
            artifact_service.add_artifact(
                notebook,
                source_channel=CollectionItemSourceChannel.CODE,
            )

    def test_remove_artifact(self, artifact_service, conversation):
        """Test removing an artifact item."""
        collection = artifact_service.get_or_create_artifacts(conversation)
        result = artifact_service.add_artifact(
            collection,
            source_channel=CollectionItemSourceChannel.CODE,
        )

        removed = artifact_service.remove_artifact(collection, result.item.id)

        assert removed is True
        assert not DocumentCollectionItem.objects.filter(id=result.item.id).exists()

    def test_remove_nonexistent_artifact(self, artifact_service, conversation):
        """Test removing a non-existent artifact returns False."""
        collection = artifact_service.get_or_create_artifacts(conversation)

        removed = artifact_service.remove_artifact(collection, 99999)

        assert removed is False

    def test_list_artifacts(self, artifact_service, conversation):
        """Test listing artifacts in a collection."""
        collection = artifact_service.get_or_create_artifacts(conversation)

        # Add multiple artifacts
        for i in range(3):
            artifact_service.add_artifact(
                collection,
                source_channel=CollectionItemSourceChannel.CODE,
                source_metadata={'index': i},
            )

        items = artifact_service.list_artifacts(collection)

        assert len(items) == 3
        # Should be ordered by position
        assert items[0].position < items[1].position < items[2].position


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_or_create_artifacts_for_conversation(self, conversation, user):
        """Test convenience function for conversations."""
        collection = get_or_create_artifacts_for_conversation(conversation, user)

        assert collection is not None
        assert 'Test Conversation' in collection.name

    def test_get_or_create_artifacts_for_workflow_run(self, workflow_run, user):
        """Test convenience function for workflow runs."""
        collection = get_or_create_artifacts_for_workflow_run(workflow_run, user)

        assert collection is not None
        assert 'test-workflow' in collection.name
