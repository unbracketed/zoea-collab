"""
Tests for document models.

This module tests the document model hierarchy including:
- Polymorphic queries with select_subclasses()
- Organization scoping across hierarchy
- Type-specific functionality
- File handling for Image and PDF documents
"""

import json
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from organizations.models import Organization, OrganizationUser

from accounts.models import Account
from file_search.types import SearchResult, SourceReference
from projects.models import Project
from .models import (
    Collection,
    Document,
    Image,
    PDF,
    TextDocument,
    Markdown,
    CSV,
    D2Diagram,
    ReactFlowDiagram,
    Folder,
)

User = get_user_model()


@pytest.fixture
def organization():
    """Create a test organization (Account extends Organization)."""
    return Account.objects.create(name="Test Organization")


@pytest.fixture
def other_organization():
    """Create another test organization for multi-tenant testing."""
    return Account.objects.create(name="Other Organization")


@pytest.fixture
def user(organization):
    """Create a test user in the organization."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    OrganizationUser.objects.create(
        organization=organization,
        user=user
    )
    return user


@pytest.fixture
def other_user(other_organization):
    """Create a user in a different organization."""
    user = User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123"
    )
    OrganizationUser.objects.create(
        organization=other_organization,
        user=user
    )
    return user


@pytest.fixture
def collection(organization, user):
    """Create a test collection."""
    return Collection.objects.create(
        organization=organization,
        name="Test Collection",
        description="A test collection",
        created_by=user
    )


@pytest.mark.django_db
class TestDocumentHierarchy:
    """Test multi-table inheritance and polymorphic queries."""

    def test_create_different_document_types(self, organization, user):
        """Test creating various document types."""
        # Create different document types
        markdown = Markdown.objects.create(
            organization=organization,
            name="test.md",
            content="# Test Markdown",
            created_by=user
        )
        csv_doc = CSV.objects.create(
            organization=organization,
            name="test.csv",
            content="col1,col2\nval1,val2",
            has_header=True,
            delimiter=",",
            created_by=user
        )
        d2_diagram = D2Diagram.objects.create(
            organization=organization,
            name="test.d2",
            content="A -> B: Connection",
            created_by=user
        )

        assert markdown.pk is not None
        assert csv_doc.pk is not None
        assert d2_diagram.pk is not None

    def test_polymorphic_query(self, organization, user):
        """Test querying base Document model returns all types."""
        # Create different document types
        Markdown.objects.create(
            organization=organization,
            name="test.md",
            content="# Test",
            created_by=user
        )
        CSV.objects.create(
            organization=organization,
            name="test.csv",
            content="a,b,c",
            created_by=user
        )
        D2Diagram.objects.create(
            organization=organization,
            name="test.d2",
            content="A -> B",
            created_by=user
        )

        # Query base class returns all types
        documents = Document.objects.select_subclasses()
        assert documents.count() == 3

        # Verify we get actual subclass instances
        doc_types = [type(doc).__name__ for doc in documents]
        assert 'Markdown' in doc_types
        assert 'CSV' in doc_types
        assert 'D2Diagram' in doc_types

    def test_organization_scoping(self, organization, other_organization, user, other_user):
        """Test that organization scoping works across hierarchy."""
        # Create documents in different organizations
        Markdown.objects.create(
            organization=organization,
            name="org1_doc.md",
            content="Org 1",
            created_by=user
        )
        Markdown.objects.create(
            organization=other_organization,
            name="org2_doc.md",
            content="Org 2",
            created_by=other_user
        )

        # Query with organization scoping
        user_docs = Document.objects.for_user(user)
        other_docs = Document.objects.for_user(other_user)

        assert user_docs.count() == 1
        assert other_docs.count() == 1

        # Verify no overlap
        assert not set(user_docs).intersection(set(other_docs))

    def test_get_type_name(self, organization, user):
        """Test get_type_name method returns correct type."""
        markdown = Markdown.objects.create(
            organization=organization,
            name="test.md",
            content="# Test",
            created_by=user
        )
        csv_doc = CSV.objects.create(
            organization=organization,
            name="test.csv",
            content="a,b",
            created_by=user
        )

        assert markdown.get_type_name() == 'Markdown'
        assert csv_doc.get_type_name() == 'CSV'


@pytest.mark.django_db
class TestImageDocument:
    """Test Image document type."""

    def test_create_image_document(self, organization, user):
        """Test creating an image document."""
        # Create a fake image file
        image_content = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        image_file = SimpleUploadedFile(
            "test.gif",
            image_content,
            content_type="image/gif"
        )

        image = Image.objects.create(
            organization=organization,
            name="test_image.gif",
            image_file=image_file,
            created_by=user
        )

        assert image.pk is not None
        assert image.image_file.name is not None
        assert 'images/' in image.image_file.name

        # Cleanup
        image.image_file.delete()

    def test_image_dimensions(self, organization, user):
        """Test that image dimensions are auto-populated."""
        # Create a minimal 1x1 GIF
        image_content = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
            b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
            b'\x02\x4c\x01\x00\x3b'
        )
        image_file = SimpleUploadedFile(
            "test.gif",
            image_content,
            content_type="image/gif"
        )

        image = Image.objects.create(
            organization=organization,
            name="test_dimensions.gif",
            image_file=image_file,
            created_by=user
        )

        assert image.width == 1
        assert image.height == 1

        # Cleanup
        image.image_file.delete()


@pytest.mark.django_db
class TestPDFDocument:
    """Test PDF document type."""

    def test_create_pdf_document(self, organization, user):
        """Test creating a PDF document."""
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_file = SimpleUploadedFile(
            "test.pdf",
            pdf_content,
            content_type="application/pdf"
        )

        pdf = PDF.objects.create(
            organization=organization,
            name="test_document.pdf",
            pdf_file=pdf_file,
            page_count=5,
            created_by=user
        )

        assert pdf.pk is not None
        assert pdf.pdf_file.name is not None
        assert 'pdfs/' in pdf.pdf_file.name
        assert pdf.page_count == 5

        # Cleanup
        pdf.pdf_file.delete()


@pytest.mark.django_db
class TestTextDocuments:
    """Test text-based document types."""

    def test_markdown_document(self, organization, user):
        """Test Markdown document creation."""
        markdown = Markdown.objects.create(
            organization=organization,
            name="readme.md",
            content="# README\n\nThis is a test.",
            created_by=user
        )

        assert markdown.pk is not None
        assert markdown.content == "# README\n\nThis is a test."
        assert isinstance(markdown, TextDocument)

    def test_csv_document(self, organization, user):
        """Test CSV document creation with metadata."""
        csv_doc = CSV.objects.create(
            organization=organization,
            name="data.csv",
            content="name,age,city\nJohn,30,NYC\nJane,25,LA",
            has_header=True,
            delimiter=",",
            created_by=user
        )

        assert csv_doc.pk is not None
        assert csv_doc.has_header is True
        assert csv_doc.delimiter == ","
        assert isinstance(csv_doc, TextDocument)

    def test_d2_diagram(self, organization, user):
        """Test D2 diagram document creation."""
        d2 = D2Diagram.objects.create(
            organization=organization,
            name="architecture.d2",
            content="Frontend -> Backend: API Calls\nBackend -> Database: Queries",
            created_by=user
        )

        assert d2.pk is not None
        assert d2.diagram_type == 'd2'
        assert isinstance(d2, TextDocument)

    def test_react_flow_diagram(self, organization, user):
        """Test React Flow diagram document creation."""
        rf = ReactFlowDiagram.objects.create(
            organization=organization,
            name="workflow.json",
            content='{"nodes": [], "edges": []}',
            react_flow_version="11.0.0",
            created_by=user
        )

        assert rf.pk is not None
        assert rf.diagram_type == 'react_flow'
        assert rf.react_flow_version == "11.0.0"
        assert isinstance(rf, TextDocument)


@pytest.mark.django_db
class TestCollection:
    """Test Collection model."""

    def test_create_collection(self, organization, user):
        """Test creating a collection."""
        collection = Collection.objects.create(
            organization=organization,
            name="Test Collection",
            description="A test collection",
            created_by=user
        )

        assert collection.pk is not None
        assert str(collection) == f"Test Collection ({organization.name})"

    def test_collection_documents_relationship(self, organization, user, collection):
        """Test adding documents to collection."""
        markdown = Markdown.objects.create(
            organization=organization,
            name="doc1.md",
            content="Content 1",
            created_by=user
        )
        csv_doc = CSV.objects.create(
            organization=organization,
            name="doc2.csv",
            content="a,b,c",
            created_by=user
        )

        # Add documents to collection
        collection.documents.add(markdown, csv_doc)

        assert collection.documents.count() == 2
        # Use select_subclasses to get actual subclass instances
        docs = collection.documents.select_subclasses()
        assert markdown in docs
        assert csv_doc in docs

    def test_collection_organization_scoping(self, organization, other_organization, user, other_user):
        """Test collection organization scoping."""
        Collection.objects.create(
            organization=organization,
            name="Org1 Collection",
            created_by=user
        )
        Collection.objects.create(
            organization=other_organization,
            name="Org2 Collection",
            created_by=other_user
        )

        user_collections = Collection.objects.for_user(user)
        other_collections = Collection.objects.for_user(other_user)

        assert user_collections.count() == 1
        assert other_collections.count() == 1
        assert not set(user_collections).intersection(set(other_collections))


@pytest.mark.django_db
class TestInheritancePerformance:
    """Test that select_subclasses() efficiently loads all types."""

    def test_select_subclasses_efficiency(self, organization, user):
        """Test that select_subclasses reduces queries."""
        # Create multiple document types
        for i in range(3):
            Markdown.objects.create(
                organization=organization,
                name=f"md{i}.md",
                content=f"Content {i}",
                created_by=user
            )
            CSV.objects.create(
                organization=organization,
                name=f"csv{i}.csv",
                content="a,b,c",
                created_by=user
            )
            D2Diagram.objects.create(
                organization=organization,
                name=f"d2_{i}.d2",
                content="A -> B",
                created_by=user
            )

        # Query with select_subclasses should be efficient
        documents = Document.objects.select_subclasses()
        assert documents.count() == 9

        # Accessing subclass fields shouldn't trigger additional queries
        # (This would be tested with django-debug-toolbar or assertNumQueries
        # in a real scenario, but we verify the instances are correct types)
        for doc in documents:
            assert isinstance(doc, (Markdown, CSV, D2Diagram))
            # Access subclass-specific fields
            if isinstance(doc, Markdown):
                assert hasattr(doc, 'content')
            elif isinstance(doc, CSV):
                assert hasattr(doc, 'has_header')
            elif isinstance(doc, D2Diagram):
                assert hasattr(doc, 'diagram_type')


@pytest.mark.django_db
def test_create_d2_document_api(client, organization, user):
    """Ensure the D2 document creation endpoint persists a document."""

    project = Project.objects.create(
        organization=organization,
        name="Canvas Project",
        working_directory="/tmp/canvas",
        created_by=user,
    )

    client.force_login(user)

    payload = {
        "name": "Sample Diagram",
        "description": "Created from canvas",
        "content": "a -> b: link",
        "project_id": project.id,
    }

    response = client.post(
        "/api/documents/d2/create",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["document_type"] == "D2Diagram"
    assert data["organization_id"] == organization.id


@pytest.mark.django_db
def test_create_markdown_document_api(client, organization, user):
    """Ensure markdown creation endpoint persists a document."""

    project = Project.objects.create(
        organization=organization,
        name="Markdown Project",
        working_directory="/tmp/md",
        created_by=user,
    )

    client.force_login(user)

    payload = {
        "name": "Notes",
        "description": "Markdown saved via API",
        "content": "# Title\nSome text",
        "project_id": project.id,
    }

    response = client.post(
        "/api/documents/markdown/create",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Notes"
    assert data["document_type"] == "Markdown"


@pytest.mark.django_db
def test_upload_image_document_api(client, organization, user):
    """Ensure the image upload endpoint persists an Image document with dimensions."""

    project = Project.objects.create(
        organization=organization,
        name="Image Project",
        working_directory="/tmp/images",
        created_by=user,
    )

    client.force_login(user)

    image_content = (
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04'
        b'\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02'
        b'\x02\x4c\x01\x00\x3b'
    )
    image_file = SimpleUploadedFile(
        "upload.gif",
        image_content,
        content_type="image/gif"
    )

    response = client.post(
        "/api/documents/images/upload",
        data={
            "name": "Upload Test",
            "description": "Uploaded through API",
            "project_id": project.id,
            "image_file": image_file,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Upload Test"
    assert data["document_type"] == "Image"
    assert data["organization_id"] == organization.id
    assert data["width"] == 1
    assert data["height"] == 1
    assert data["image_file"].startswith("http")

    created_image = Image.objects.get(id=data["id"])
    created_image.image_file.delete(save=False)
    created_image.delete()


@pytest.mark.django_db
def test_folder_creation_and_listing(client, organization, user):
    project = Project.objects.create(
        organization=organization,
        name="Folder Project",
        working_directory="/tmp/folders",
        created_by=user,
    )

    client.force_login(user)

    response = client.post(
        "/api/documents/folders",
        data=json.dumps({"name": "Root", "project_id": project.id}),
        content_type="application/json",
    )
    assert response.status_code == 200
    folder_id = response.json()["id"]

    list_resp = client.get(f"/api/documents/folders?project_id={project.id}")
    assert list_resp.status_code == 200
    assert any(f["id"] == folder_id for f in list_resp.json())


@pytest.mark.django_db
def test_list_documents_filtered_by_folder(client, organization, user):
    project = Project.objects.create(
        organization=organization,
        name="Filter Project",
        working_directory="/tmp/filter",
        created_by=user,
    )
    folder = Folder.objects.create(
        name="Folder A",
        project=project,
        organization=organization,
        created_by=user,
    )
    doc = Markdown.objects.create(
        organization=organization,
        project=project,
        name="Doc",
        content="Body",
        created_by=user,
        folder=folder,
    )

    client.force_login(user)
    resp = client.get(f"/api/documents?folder_id={folder.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["documents"][0]["id"] == doc.id


@pytest.mark.django_db
def test_move_document_between_folders(client, organization, user):
    project = Project.objects.create(
        organization=organization,
        name="Move Project",
        working_directory="/tmp/move",
        created_by=user,
    )
    folder = Folder.objects.create(
        name="Folder",
        project=project,
        organization=organization,
        created_by=user,
    )
    doc = Markdown.objects.create(
        organization=organization,
        project=project,
        name="Doc",
        content="Body",
        created_by=user,
    )

    client.force_login(user)
    resp = client.post(
        f"/api/documents/{doc.id}/move",
        data=json.dumps({"folder_id": folder.id}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    moved = resp.json()
    assert moved["folder_id"] == folder.id


@pytest.mark.django_db
def test_list_documents_validates_folder_belongs_to_project(client, organization, user):
    """Folder from another project should be rejected."""
    project_a = Project.objects.create(
        organization=organization,
        name="Project A",
        working_directory="/tmp/a",
        created_by=user,
    )
    project_b = Project.objects.create(
        organization=organization,
        name="Project B",
        working_directory="/tmp/b",
        created_by=user,
    )
    folder_b = Folder.objects.create(
        project=project_b,
        organization=organization,
        name="B Folder",
        created_by=user,
    )

    client.force_login(user)

    resp = client.get(
        f"/api/documents?project_id={project_a.id}&folder_id={folder_b.id}"
    )
    assert resp.status_code == 400
    assert "Folder must belong" in resp.json()["detail"]


@pytest.mark.django_db
def test_create_folder_parent_must_match_project(client, organization, user):
    """Creating a folder with a parent from a different project fails."""
    project = Project.objects.create(
        organization=organization,
        name="Folder Project",
        working_directory="/tmp/folder-mismatch",
        created_by=user,
    )
    other_project = Project.objects.create(
        organization=organization,
        name="Other Project",
        working_directory="/tmp/folder-mismatch2",
        created_by=user,
    )
    parent = Folder.objects.create(
        name="Parent",
        project=other_project,
        organization=organization,
        created_by=user,
    )

    client.force_login(user)
    payload = {
        "name": "Child",
        "project_id": project.id,
        "parent_id": parent.id,
    }
    resp = client.post(
        "/api/documents/folders",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert "Parent folder must belong to the same project" in resp.json()["detail"]


@pytest.mark.django_db
def test_file_search_returns_sources(client, organization, user, settings):
    """Gemini file search endpoint should return parsed citations."""
    project = Project.objects.create(
        organization=organization,
        name="Searchable Project",
        working_directory="/tmp/searchable",
        created_by=user,
        gemini_store_id="fileSearchStores/test-store",
        gemini_store_name="Test Store",
    )

    client.force_login(user)

    with patch("documents.api.FileSearchRegistry") as registry_cls:
        store_mock = Mock()
        store_mock.backend_name = "gemini"
        store_mock.search.return_value = SearchResult(
            answer="This is a synthesized answer.",
            sources=[
                SourceReference(
                    title="Doc Title",
                    uri="files/doc-123",
                    excerpt="Relevant snippet from the document.",
                )
            ],
        )
        registry_cls.get.return_value = store_mock

        resp = client.post(
            "/api/documents/file-search",
            data=json.dumps({"query": "What is this project about?", "project_id": project.id}),
            content_type="application/json",
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "This is a synthesized answer."
    assert data["store_id"] == project.gemini_store_id
    assert data["model_id"] == settings.GEMINI_MODEL_ID
    assert data["sources"][0]["title"] == "Doc Title"
    assert data["sources"][0]["uri"] == "files/doc-123"

    store_mock.search.assert_called_once_with(
        store_id=project.gemini_store_id,
        query="What is this project about?",
        max_results=5,
        filters=None,
    )


@pytest.mark.django_db
def test_file_search_requires_store_id(client, organization, user):
    """Projects without a Gemini store should be rejected."""
    project = Project.objects.create(
        organization=organization,
        name="No Store Project",
        working_directory="/tmp/no-store",
        created_by=user,
    )

    client.force_login(user)

    resp = client.post(
        "/api/documents/file-search",
        data=json.dumps({"query": "test", "project_id": project.id}),
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert "not synced to file search" in resp.json()["detail"]


@pytest.mark.django_db
def test_file_search_handles_service_error(client, organization, user):
    """Service failures should surface as 502 responses."""
    project = Project.objects.create(
        organization=organization,
        name="Error Project",
        working_directory="/tmp/error-project",
        created_by=user,
        gemini_store_id="fileSearchStores/error-store",
    )

    client.force_login(user)

    with patch("documents.api.FileSearchRegistry") as registry_cls:
        store_mock = Mock()
        store_mock.backend_name = "chromadb"
        store_mock.search.side_effect = Exception("API exploded")
        registry_cls.get.return_value = store_mock

        resp = client.post(
            "/api/documents/file-search",
            data=json.dumps({"query": "trigger error", "project_id": project.id}),
            content_type="application/json",
        )

    assert resp.status_code == 502
    assert "File search query failed" in resp.json()["detail"]
