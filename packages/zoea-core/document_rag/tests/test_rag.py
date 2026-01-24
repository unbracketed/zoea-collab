from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from organizations.models import Organization, OrganizationUser

from document_rag.models import RAGSession
from document_rag.telemetry import summarize_smolagents_run
from document_rag.session_manager import RAGSessionManager
from documents.models import Collection, Document, Folder
from projects.models import Project


@pytest.mark.django_db
def test_rag_resolve_documents_single_is_scoped_to_project():
    User = get_user_model()
    user = User.objects.create_user("rag@example.com", "rag@example.com", "password123")
    organization = Organization.objects.create(name="RAG Org", slug="rag-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project_a = Project.objects.create(
        organization=organization,
        name="Project A",
        working_directory="/tmp/project-a",
        created_by=user,
    )
    project_b = Project.objects.create(
        organization=organization,
        name="Project B",
        working_directory="/tmp/project-b",
        created_by=user,
    )

    doc = Document.objects.create(
        organization=organization,
        project=project_a,
        name="Doc A",
        description="",
        created_by=user,
    )

    manager = RAGSessionManager()

    # Document should not be visible in project_b context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.SINGLE,
        doc.id,
        organization=organization,
        project=project_b,
        user=user,
    )
    assert docs == []

    # Document should be visible in project_a context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.SINGLE,
        doc.id,
        organization=organization,
        project=project_a,
        user=user,
    )
    assert [d.id for d in docs] == [doc.id]


@pytest.mark.django_db
def test_rag_resolve_documents_folder_is_scoped_to_project():
    User = get_user_model()
    user = User.objects.create_user("folder@example.com", "folder@example.com", "password123")
    organization = Organization.objects.create(name="Folder Org", slug="folder-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project_a = Project.objects.create(
        organization=organization,
        name="Project A",
        working_directory="/tmp/project-a",
        created_by=user,
    )
    project_b = Project.objects.create(
        organization=organization,
        name="Project B",
        working_directory="/tmp/project-b",
        created_by=user,
    )

    folder = Folder.objects.create(
        name="Folder A",
        project=project_a,
        organization=organization,
        created_by=user,
    )
    doc = Document.objects.create(
        organization=organization,
        project=project_a,
        name="Doc A",
        description="",
        created_by=user,
        folder=folder,
    )

    manager = RAGSessionManager()

    # Folder should not be visible in project_b context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.FOLDER,
        folder.id,
        organization=organization,
        project=project_b,
        user=user,
    )
    assert docs == []

    # Folder should be visible in project_a context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.FOLDER,
        folder.id,
        organization=organization,
        project=project_a,
        user=user,
    )
    assert [d.id for d in docs] == [doc.id]


@pytest.mark.django_db
def test_rag_resolve_documents_collection_is_scoped_to_project():
    User = get_user_model()
    user = User.objects.create_user(
        "collection@example.com", "collection@example.com", "password123"
    )
    organization = Organization.objects.create(name="Collection Org", slug="collection-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project_a = Project.objects.create(
        organization=organization,
        name="Project A",
        working_directory="/tmp/project-a",
        created_by=user,
    )
    project_b = Project.objects.create(
        organization=organization,
        name="Project B",
        working_directory="/tmp/project-b",
        created_by=user,
    )

    collection = Collection.objects.create(
        organization=organization,
        project=project_a,
        name="Collection A",
        description="",
        created_by=user,
    )
    doc = Document.objects.create(
        organization=organization,
        project=project_a,
        name="Doc A",
        description="",
        created_by=user,
    )
    doc.collections.add(collection)

    manager = RAGSessionManager()

    # Collection should not be visible in project_b context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.COLLECTION,
        collection.id,
        organization=organization,
        project=project_b,
        user=user,
    )
    assert docs == []

    # Collection should be visible in project_a context
    docs = async_to_sync(manager._resolve_documents)(
        RAGSession.ContextType.COLLECTION,
        collection.id,
        organization=organization,
        project=project_a,
        user=user,
    )
    assert [d.id for d in docs] == [doc.id]


def test_summarize_smolagents_run_counts_tool_calls_and_errors():
    from smolagents.agents import RunResult
    from smolagents.monitoring import Timing, TokenUsage

    run_result = RunResult(
        output="ok",
        state="success",
        steps=[
            {
                "step_number": 1,
                "tool_calls": [
                    {"type": "function", "id": "1", "function": {"name": "document_retriever", "arguments": "{}"}},
                    {"type": "function", "id": "2", "function": {"name": "document_retriever", "arguments": "{}"}},
                ],
                "error": None,
            },
            {
                "step_number": 2,
                "tool_calls": [
                    {"type": "function", "id": "3", "function": {"name": "image_analyzer", "arguments": "{}"}},
                ],
                "error": {"message": "boom"},
            },
        ],
        token_usage=TokenUsage(input_tokens=10, output_tokens=5),
        timing=Timing(start_time=1.0, end_time=3.5),
    )

    summary = summarize_smolagents_run(run_result)
    assert summary["state"] == "success"
    assert summary["token_usage"]["total_tokens"] == 15
    assert summary["timing"]["duration"] == 2.5
    assert summary["steps"]["count"] == 2
    assert summary["steps"]["error_count"] == 1
    assert summary["steps"]["tool_calls_by_name"] == {
        "document_retriever": 2,
        "image_analyzer": 1,
    }


@pytest.mark.django_db
def test_rag_agent_service_saves_telemetry_on_assistant_message():
    from document_rag.agent_service import DocumentRAGAgentService
    from document_rag.models import RAGSessionMessage
    from smolagents.agents import RunResult
    from smolagents.monitoring import Timing, TokenUsage

    User = get_user_model()
    user = User.objects.create_user("telemetry@example.com", "telemetry@example.com", "password123")
    organization = Organization.objects.create(name="Telemetry Org", slug="telemetry-org")
    OrganizationUser.objects.create(organization=organization, user=user, is_admin=True)

    project = Project.objects.create(
        organization=organization,
        name="Telemetry Project",
        working_directory="/tmp/telemetry",
        created_by=user,
    )

    session = RAGSession.objects.create(
        organization=organization,
        project=project,
        created_by=user,
        status=RAGSession.Status.ACTIVE,
        context_type=RAGSession.ContextType.SINGLE,
        context_id=1,
        document_ids=[],
        gemini_store_id="store",
    )

    run_result = RunResult(
        output="hello",
        state="success",
        steps=[],
        token_usage=TokenUsage(input_tokens=1, output_tokens=2),
        timing=Timing(start_time=0.0, end_time=1.0),
    )

    class DummyRetriever:
        def __init__(self, *args, **kwargs):
            self.last_retrieved_sources = []
            self.telemetry = {"calls": 0}

    class DummyImageAnalyzer:
        def __init__(self, *args, **kwargs):
            pass

    class DummyAgent:
        def __init__(self, *args, **kwargs):
            self.logs = []

        def run(self, *args, **kwargs):
            return run_result

    with patch("document_rag.agent_service.DocumentRetrieverTool", DummyRetriever), patch(
        "document_rag.agent_service.ImageAnalyzerTool", DummyImageAnalyzer
    ), patch("document_rag.agent_service.CodeAgent", DummyAgent), patch(
        "document_rag.agent_service.FileSearchRegistry"
    ) as registry_cls, patch.object(
        DocumentRAGAgentService,
        "_create_smolagents_model",
        return_value=MagicMock(),
    ):
        registry_cls.get.return_value = SimpleNamespace(backend_name="chromadb")
        service = DocumentRAGAgentService(session, project=project)
        response = async_to_sync(service.chat)("hi")

        msg = async_to_sync(service.save_message)(
            role=RAGSessionMessage.Role.ASSISTANT,
            content=response.response,
            sources=response.sources,
            thinking_steps=response.thinking_steps,
            telemetry=response.telemetry,
        )

        assert msg.telemetry["smolagents"]["token_usage"]["total_tokens"] == 3
