"""
Tests for document import service.
"""

import zipfile

import pytest
from django.contrib.auth import get_user_model
from organizations.models import OrganizationUser

from accounts.models import Account
from documents.import_service import DocumentImportService, ImportLimitError
from documents.models import Document, Folder, PDF
from projects.models import Project


User = get_user_model()


@pytest.fixture
def organization():
    return Account.objects.create(name="Import Org")


@pytest.fixture
def user(organization):
    user = User.objects.create_user(
        username="importer",
        email="importer@example.com",
        password="testpass123",
    )
    OrganizationUser.objects.create(organization=organization, user=user)
    return user


@pytest.fixture
def project(organization, user):
    return Project.objects.create(
        organization=organization,
        name="Import Project",
        created_by=user,
    )


@pytest.mark.django_db
def test_import_directory_creates_documents(tmp_path, organization, project, user, settings):
    settings.ZOEA_IMPORT_ALLOWED_ROOTS = [str(tmp_path)]

    root = tmp_path / "import-root"
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True)

    (docs_dir / "readme.md").write_text("# Hello")
    (docs_dir / "data.csv").write_text("a,b\n1,2")
    (root / "report.pdf").write_bytes(b"%PDF-1.4\n%EOF\n")
    (root / "diagram.mmd").write_text("graph TD; A-->B;")

    service = DocumentImportService(
        organization=organization,
        project=project,
        created_by=user,
        create_root_folder=True,
    )

    summary = service.import_directory(str(root))

    assert summary.created == 3
    assert summary.skipped == 1
    assert summary.total_files == 4

    root_folder = Folder.objects.get(name="import-root")
    docs_folder = Folder.objects.get(parent=root_folder, name="docs")

    docs = Document.objects.select_subclasses().filter(project=project)
    names = {doc.name for doc in docs}
    assert names == {"readme", "data", "report"}

    pdf_doc = PDF.objects.get(name="report")
    assert pdf_doc.folder == root_folder
    assert docs_folder.project == project


@pytest.mark.django_db
def test_import_archive_single_root(tmp_path, organization, project, user, settings):
    settings.ZOEA_IMPORT_ALLOWED_ROOTS = [str(tmp_path)]

    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("root/readme.md", "# Hello")
        archive.writestr("root/report.pdf", b"%PDF-1.4\n%EOF\n")

    service = DocumentImportService(
        organization=organization,
        project=project,
        created_by=user,
        create_root_folder=True,
    )

    summary = service.import_archive(archive_path)

    assert summary.created == 2
    assert summary.total_files == 2

    root_folder = Folder.objects.get(name="root")
    docs = Document.objects.select_subclasses().filter(folder=root_folder)
    assert {doc.name for doc in docs} == {"readme", "report"}


@pytest.mark.django_db
def test_import_directory_enforces_file_size_limit(tmp_path, organization, project, user, settings):
    settings.ZOEA_IMPORT_ALLOWED_ROOTS = [str(tmp_path)]
    settings.ZOEA_IMPORT_MAX_FILE_SIZE_BYTES = 1

    root = tmp_path / "import-large"
    root.mkdir()
    (root / "too-big.md").write_text("ab")

    service = DocumentImportService(
        organization=organization,
        project=project,
        created_by=user,
        create_root_folder=True,
    )

    with pytest.raises(ImportLimitError):
        service.import_directory(str(root))
