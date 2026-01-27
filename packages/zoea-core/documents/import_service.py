"""
Import documents from filesystem directories or archive files.

Handles validation, folder creation, and document type mapping with
configurable limits from Django settings.
"""

from __future__ import annotations

import logging
import os
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.files.base import ContentFile

from .models import (
    CSV,
    D2Diagram,
    Document,
    Folder,
    Image,
    Markdown,
    PDF,
    SpreadsheetDocument,
    WordDocument,
)


TEXT_EXTENSION_MAP = {
    ".md": Markdown,
    ".markdown": Markdown,
    ".txt": Markdown,
    ".yaml": Markdown,
    ".yml": Markdown,
    ".json": Markdown,
    ".csv": CSV,
    ".d2": D2Diagram,
}

BINARY_EXTENSION_MAP = {
    ".pdf": PDF,
    ".docx": WordDocument,
    ".xlsx": SpreadsheetDocument,
    ".png": Image,
    ".jpg": Image,
    ".jpeg": Image,
    ".gif": Image,
    ".bmp": Image,
    ".webp": Image,
}

SUPPORTED_EXTENSIONS = set(TEXT_EXTENSION_MAP) | set(BINARY_EXTENSION_MAP)

DEFAULT_IGNORED_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__MACOSX",
    ".DS_Store",
    "node_modules",
    "__pycache__",
}

MAX_ISSUES = 100

logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Base import error."""


class ImportValidationError(ImportError):
    """Validation errors for import inputs."""


class ImportLimitError(ImportError):
    """Raised when import exceeds configured limits."""


@dataclass
class ImportIssue:
    path: str
    reason: str
    status: str = "skipped"
    detail: str | None = None


@dataclass
class ImportSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    total_files: int = 0
    total_size: int = 0
    root_folder_id: int | None = None
    root_folder_path: str | None = None
    issues: list[ImportIssue] = field(default_factory=list)


class DocumentImportService:
    """Service for importing documents into Zoea Collab."""

    def __init__(
        self,
        *,
        organization,
        project,
        created_by,
        base_folder: Folder | None = None,
        create_root_folder: bool = True,
        root_folder_name: str | None = None,
        on_conflict: str = "rename",
    ):
        self.organization = organization
        self.project = project
        self.created_by = created_by
        self.base_folder = base_folder
        self.create_root_folder = create_root_folder
        self.root_folder_name = root_folder_name
        self.on_conflict = on_conflict
        self.folder_cache: dict[tuple[int | None, str], Folder] = {}
        self.imported_documents: list[Document] = []

        if self.on_conflict not in {"skip", "rename", "overwrite"}:
            raise ImportValidationError(f"Invalid on_conflict value: {self.on_conflict}")

        self.max_file_size = int(
            getattr(settings, "ZOEA_IMPORT_MAX_FILE_SIZE_BYTES", 50 * 1024 * 1024)
        )
        self.max_total_size = int(
            getattr(settings, "ZOEA_IMPORT_MAX_TOTAL_SIZE_BYTES", 10 * 1024 * 1024 * 1024)
        )
        self.max_file_count = int(
            getattr(settings, "ZOEA_IMPORT_MAX_FILE_COUNT", 100000)
        )
        self.max_depth = int(getattr(settings, "ZOEA_IMPORT_MAX_DEPTH", 10))

        allowed_roots = getattr(settings, "ZOEA_IMPORT_ALLOWED_ROOTS", [])
        self.allowed_roots = [
            Path(root).expanduser().resolve()
            for root in allowed_roots
            if str(root).strip()
        ]

    def import_directory(self, directory_path: str, *, follow_symlinks: bool = False) -> ImportSummary:
        base_path = Path(directory_path).expanduser().resolve()
        self._validate_directory(base_path)

        summary = ImportSummary()
        root_folder = self._resolve_root_folder(base_path.name)
        if root_folder:
            summary.root_folder_id = root_folder.id
            summary.root_folder_path = root_folder.get_path()

        for root, dirnames, filenames in os.walk(base_path, followlinks=follow_symlinks):
            current_path = Path(root)
            rel_dir = current_path.relative_to(base_path)

            if follow_symlinks:
                resolved_current = current_path.resolve()
                if not self._is_within_path(resolved_current, base_path):
                    dirnames[:] = []
                    continue

            if self._should_ignore_path(rel_dir):
                dirnames[:] = []
                continue

            if not follow_symlinks:
                dirnames[:] = [
                    name for name in dirnames if not (current_path / name).is_symlink()
                ]

            dirnames[:] = [name for name in dirnames if not self._should_ignore_name(name)]

            for filename in filenames:
                file_path = current_path / filename
                rel_path = file_path.relative_to(base_path)

                if self._should_ignore_path(rel_path):
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "ignored")
                    continue

                if not follow_symlinks and file_path.is_symlink():
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "symlink_skipped")
                    continue
                if follow_symlinks and not self._is_within_path(file_path.resolve(), base_path):
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "symlink_outside_root")
                    continue

                depth = max(len(rel_path.parts) - 1, 0)
                if depth > self.max_depth:
                    raise ImportLimitError(f"Path depth exceeds limit: {rel_path}")

                try:
                    file_size = file_path.stat().st_size
                except OSError as exc:
                    summary.failed += 1
                    self._record_issue(summary, rel_path, "stat_failed", detail=str(exc), status="failed")
                    continue

                summary.total_files += 1
                summary.total_size += file_size
                self._enforce_limits(summary, file_size, rel_path=rel_path)

                extension = rel_path.suffix.lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "unsupported_extension")
                    continue

                parent_folder = self._resolve_parent_folder(rel_path.parent, root_folder)
                self._import_file_from_path(
                    summary=summary,
                    rel_path=rel_path,
                    file_path=file_path,
                    extension=extension,
                    parent_folder=parent_folder,
                )

        self._index_imported_documents()
        return summary

    def import_archive(self, archive_path: str | Path | object) -> ImportSummary:
        summary = ImportSummary()
        archive_name = self._get_archive_name(archive_path)
        archive_type = self._detect_archive_type(archive_name)

        if archive_type == "zip":
            return self._import_zip_archive(archive_path, archive_name, summary)
        if archive_type == "tar":
            return self._import_tar_archive(archive_path, archive_name, summary)

        raise ImportValidationError(f"Unsupported archive type: {archive_name}")

    def _import_zip_archive(
        self,
        archive_path: str | Path | object,
        archive_name: str,
        summary: ImportSummary,
    ) -> ImportSummary:
        file_obj = self._open_archive_file(archive_path)
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as archive:
            entries = [info for info in archive.infolist() if not info.is_dir()]
            raw_paths = self._collect_archive_paths(entries, archive_name)
            root_name, strip_prefix = self._resolve_archive_root(raw_paths, archive_name)
            self._validate_archive_entries(entries, archive_name, summary, strip_prefix)
            root_folder = self._resolve_root_folder(root_name)
            if root_folder:
                summary.root_folder_id = root_folder.id
                summary.root_folder_path = root_folder.get_path()

            for info in entries:
                rel_path = self._clean_archive_path(info.filename, strip_prefix)
                if rel_path is None or self._should_ignore_path(rel_path):
                    summary.skipped += 1
                    self._record_issue(summary, info.filename, "ignored")
                    continue

                if self._is_zip_symlink(info):
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "symlink_skipped")
                    continue

                extension = rel_path.suffix.lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "unsupported_extension")
                    continue

                parent_folder = self._resolve_parent_folder(rel_path.parent, root_folder)

                try:
                    data = archive.read(info.filename)
                except OSError as exc:
                    summary.failed += 1
                    self._record_issue(summary, rel_path, "read_failed", detail=str(exc), status="failed")
                    continue

                self._import_file_from_bytes(
                    summary=summary,
                    rel_path=rel_path,
                    data=data,
                    extension=extension,
                    parent_folder=parent_folder,
                )

        self._index_imported_documents()
        return summary

    def _import_tar_archive(
        self,
        archive_path: str | Path | object,
        archive_name: str,
        summary: ImportSummary,
    ) -> ImportSummary:
        file_obj = self._open_archive_file(archive_path)
        if isinstance(file_obj, Path):
            archive = tarfile.open(file_obj, mode="r:*")
        else:
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
            archive = tarfile.open(fileobj=file_obj, mode="r:*")
        with archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            raw_paths = self._collect_tar_paths(members, archive_name)
            root_name, strip_prefix = self._resolve_archive_root(raw_paths, archive_name)
            self._validate_tar_entries(members, archive_name, summary, strip_prefix)
            root_folder = self._resolve_root_folder(root_name)
            if root_folder:
                summary.root_folder_id = root_folder.id
                summary.root_folder_path = root_folder.get_path()

            for member in members:
                rel_path = self._clean_archive_path(member.name, strip_prefix)
                if rel_path is None or self._should_ignore_path(rel_path):
                    summary.skipped += 1
                    self._record_issue(summary, member.name, "ignored")
                    continue

                if member.islnk() or member.issym() or member.isdev() or member.isfifo():
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "symlink_skipped")
                    continue

                extension = rel_path.suffix.lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    summary.skipped += 1
                    self._record_issue(summary, rel_path, "unsupported_extension")
                    continue

                parent_folder = self._resolve_parent_folder(rel_path.parent, root_folder)

                file_obj = archive.extractfile(member)
                if file_obj is None:
                    summary.failed += 1
                    self._record_issue(summary, rel_path, "read_failed", status="failed")
                    continue

                try:
                    data = file_obj.read()
                except OSError as exc:
                    summary.failed += 1
                    self._record_issue(summary, rel_path, "read_failed", detail=str(exc), status="failed")
                    continue

                self._import_file_from_bytes(
                    summary=summary,
                    rel_path=rel_path,
                    data=data,
                    extension=extension,
                    parent_folder=parent_folder,
                )

        self._index_imported_documents()
        return summary

    def _validate_directory(self, base_path: Path) -> None:
        if not base_path.is_absolute():
            raise ImportValidationError(f"Path must be absolute: {base_path}")
        if not base_path.exists():
            raise ImportValidationError(f"Directory does not exist: {base_path}")
        if not base_path.is_dir():
            raise ImportValidationError(f"Path is not a directory: {base_path}")
        if self.allowed_roots and not self._is_within_allowed_roots(base_path):
            raise ImportValidationError(f"Path is outside allowed roots: {base_path}")

    def _is_within_allowed_roots(self, path: Path) -> bool:
        for root in self.allowed_roots:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _is_within_path(self, path: Path, base_path: Path) -> bool:
        try:
            path.relative_to(base_path)
            return True
        except ValueError:
            return False

    def _should_ignore_name(self, name: str) -> bool:
        if name in {".", ".."}:
            return False
        return name in DEFAULT_IGNORED_NAMES or name.startswith(".")

    def _should_ignore_path(self, path: Path | PurePosixPath) -> bool:
        if not path.parts:
            return False
        return any(self._should_ignore_name(part) for part in path.parts)

    def _sanitize_name(self, name: str, fallback: str) -> str:
        cleaned = name.strip().replace("/", "-").replace("\\", "-")
        cleaned = " ".join(cleaned.split())
        cleaned = cleaned[:255]
        return cleaned or fallback

    def _resolve_root_folder(self, default_name: str | None) -> Folder | None:
        if not self.create_root_folder:
            return self.base_folder

        name = self.root_folder_name or default_name or "Imported Files"
        name = self._sanitize_name(name, "Imported Files")
        return self._get_or_create_folder(name, self.base_folder)

    def _get_or_create_folder(self, name: str, parent: Folder | None) -> Folder:
        key = (parent.id if parent else None, name)
        if key in self.folder_cache:
            return self.folder_cache[key]

        folder, _ = Folder.objects.get_or_create(
            organization=self.organization,
            project=self.project,
            parent=parent,
            name=name,
            defaults={
                "created_by": self.created_by,
                "description": "",
            },
        )
        self.folder_cache[key] = folder
        return folder

    def _resolve_parent_folder(self, rel_parent: Path | PurePosixPath, root_folder: Folder | None) -> Folder | None:
        if not rel_parent or rel_parent == Path("."):
            return root_folder

        current = root_folder
        for part in rel_parent.parts:
            if not part or part == ".":
                continue
            name = self._sanitize_name(part, "Untitled")
            current = self._get_or_create_folder(name, current)
        return current

    def _record_issue(
        self,
        summary: ImportSummary,
        path: Path | PurePosixPath | str,
        reason: str,
        detail: str | None = None,
        status: str = "skipped",
    ) -> None:
        if len(summary.issues) >= MAX_ISSUES:
            return
        summary.issues.append(
            ImportIssue(path=str(path), reason=reason, status=status, detail=detail)
        )

    def _enforce_limits(
        self,
        summary: ImportSummary,
        file_size: int,
        rel_path: Path | PurePosixPath | None = None,
    ) -> None:
        if file_size > self.max_file_size:
            suffix = f": {rel_path}" if rel_path else ""
            raise ImportLimitError(f"File size exceeds limit{suffix}")
        if summary.total_files > self.max_file_count:
            raise ImportLimitError("File count exceeds limit")
        if summary.total_size > self.max_total_size:
            raise ImportLimitError("Total size exceeds limit")

    def _import_file_from_path(
        self,
        *,
        summary: ImportSummary,
        rel_path: Path,
        file_path: Path,
        extension: str,
        parent_folder: Folder | None,
    ) -> None:
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            summary.failed += 1
            self._record_issue(summary, rel_path, "read_failed", detail=str(exc), status="failed")
            return

        self._import_file_from_bytes(
            summary=summary,
            rel_path=rel_path,
            data=data,
            extension=extension,
            parent_folder=parent_folder,
        )

    def _import_file_from_bytes(
        self,
        *,
        summary: ImportSummary,
        rel_path: Path | PurePosixPath,
        data: bytes,
        extension: str,
        parent_folder: Folder | None,
    ) -> None:
        document = None
        doc_name = self._sanitize_name(Path(rel_path.name).stem, "Untitled")
        doc_name, was_overwritten = self._handle_conflict(doc_name, parent_folder)
        if doc_name is None:
            summary.skipped += 1
            self._record_issue(summary, rel_path, "conflict_skipped")
            return

        try:
            if extension in TEXT_EXTENSION_MAP:
                content = data.decode("utf-8")
                doc_cls = TEXT_EXTENSION_MAP[extension]
                document = doc_cls(
                    organization=self.organization,
                    project=self.project,
                                        name=doc_name,
                    content=content,
                    file_size=len(data),
                    created_by=self.created_by,
                    folder=parent_folder,
                )
                document._skip_file_search = True
                document.save()
            elif extension in BINARY_EXTENSION_MAP:
                doc_cls = BINARY_EXTENSION_MAP[extension]
                django_file = ContentFile(data, name=rel_path.name)
                kwargs = {
                    "organization": self.organization,
                    "project": self.project,
                    "name": doc_name,
                    "file_size": len(data),
                    "created_by": self.created_by,
                    "folder": parent_folder,
                }
                if doc_cls is PDF:
                    document = doc_cls(pdf_file=django_file, **kwargs)
                elif doc_cls is WordDocument:
                    document = doc_cls(docx_file=django_file, **kwargs)
                elif doc_cls is SpreadsheetDocument:
                    document = doc_cls(xlsx_file=django_file, **kwargs)
                else:
                    document = doc_cls(image_file=django_file, **kwargs)
                document._skip_file_search = True
                document.save()
            else:
                summary.skipped += 1
                self._record_issue(summary, rel_path, "unsupported_extension")
                return
        except UnicodeDecodeError as exc:
            summary.failed += 1
            self._record_issue(summary, rel_path, "decode_failed", detail=str(exc), status="failed")
            return
        except Exception as exc:  # noqa: BLE001 - capture unexpected import failures
            summary.failed += 1
            self._record_issue(summary, rel_path, "create_failed", detail=str(exc), status="failed")
            return

        if was_overwritten:
            summary.updated += 1
        else:
            summary.created += 1

        if document:
            self.imported_documents.append(document)

    def _index_imported_documents(self) -> None:
        if not self.imported_documents:
            return

        try:
            from file_search.indexing import index_documents

            index_documents(self.imported_documents)
        except Exception as exc:  # noqa: BLE001 - best effort indexing
            logger.warning("Failed to batch index imported documents: %s", exc)
        finally:
            self.imported_documents = []

    def _handle_conflict(
        self,
        doc_name: str,
        parent_folder: Folder | None,
    ) -> tuple[str | None, bool]:
        queryset = Document.objects.filter(
                        folder=parent_folder,
            name=doc_name,
        )
        if not queryset.exists():
            return doc_name, False

        if self.on_conflict == "skip":
            return None, False

        if self.on_conflict == "overwrite":
            queryset.delete()
            return doc_name, True

        # rename
        base_name = doc_name
        counter = 2
        while True:
            candidate = f"{base_name} ({counter})"
            if not Document.objects.filter(
                                folder=parent_folder,
                name=candidate,
            ).exists():
                return candidate, False
            counter += 1

    def _get_archive_name(self, archive_path: str | Path | object) -> str:
        if isinstance(archive_path, (str, Path)):
            return Path(archive_path).name
        return getattr(archive_path, "name", "archive")

    def _detect_archive_type(self, archive_name: str) -> str:
        lower = archive_name.lower()
        if lower.endswith(".zip"):
            return "zip"
        if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "tar"
        raise ImportValidationError(f"Unsupported archive extension: {archive_name}")

    def _open_archive_file(self, archive_path: str | Path | object):
        if isinstance(archive_path, Path):
            path = archive_path
        elif isinstance(archive_path, str):
            path = Path(archive_path)
        else:
            return archive_path

        if not path.is_absolute():
            raise ImportValidationError(f"Archive path must be absolute: {path}")
        if not path.exists() or not path.is_file():
            raise ImportValidationError(f"Archive not found: {path}")
        if self.allowed_roots and not self._is_within_allowed_roots(path):
            raise ImportValidationError(f"Archive path is outside allowed roots: {path}")
        return path

    def _collect_archive_paths(self, entries, archive_name: str) -> list[PurePosixPath]:
        rel_paths = []
        for info in entries:
            rel_path = self._clean_archive_path(info.filename, None)
            if rel_path is None:
                raise ImportValidationError(f"Unsafe path in archive {archive_name}")
            if self._should_ignore_path(rel_path):
                continue
            rel_paths.append(rel_path)
        return rel_paths

    def _collect_tar_paths(self, members, archive_name: str) -> list[PurePosixPath]:
        rel_paths = []
        for member in members:
            rel_path = self._clean_archive_path(member.name, None)
            if rel_path is None:
                raise ImportValidationError(f"Unsafe path in archive {archive_name}")
            if self._should_ignore_path(rel_path):
                continue
            rel_paths.append(rel_path)
        return rel_paths

    def _validate_archive_entries(
        self,
        entries,
        archive_name: str,
        summary: ImportSummary,
        strip_prefix: str | None,
    ) -> None:
        for info in entries:
            raw_path = self._clean_archive_path(info.filename, None)
            if raw_path is None:
                raise ImportValidationError(f"Unsafe path in archive {archive_name}")
            if self._should_ignore_path(raw_path):
                continue

            rel_path = self._clean_archive_path(info.filename, strip_prefix)
            if rel_path is None:
                continue

            depth = max(len(rel_path.parts) - 1, 0)
            if depth > self.max_depth:
                raise ImportLimitError(f"Archive path depth exceeds limit: {rel_path}")

            file_size = info.file_size
            summary.total_files += 1
            summary.total_size += file_size
            self._enforce_limits(summary, file_size, rel_path=rel_path)

    def _validate_tar_entries(
        self,
        members,
        archive_name: str,
        summary: ImportSummary,
        strip_prefix: str | None,
    ) -> None:
        for member in members:
            raw_path = self._clean_archive_path(member.name, None)
            if raw_path is None:
                raise ImportValidationError(f"Unsafe path in archive {archive_name}")
            if self._should_ignore_path(raw_path):
                continue

            rel_path = self._clean_archive_path(member.name, strip_prefix)
            if rel_path is None:
                continue

            depth = max(len(rel_path.parts) - 1, 0)
            if depth > self.max_depth:
                raise ImportLimitError(f"Archive path depth exceeds limit: {rel_path}")

            file_size = member.size
            summary.total_files += 1
            summary.total_size += file_size
            self._enforce_limits(summary, file_size, rel_path=rel_path)

    def _resolve_archive_root(
        self,
        rel_paths: list[PurePosixPath],
        archive_name: str,
    ) -> tuple[str | None, str | None]:
        top_level = {path.parts[0] for path in rel_paths if path.parts}
        top_level_dir = None
        if len(top_level) == 1:
            candidate = next(iter(top_level))
            if all(len(path.parts) > 1 for path in rel_paths):
                top_level_dir = candidate

        if self.create_root_folder:
            if top_level_dir:
                return top_level_dir, top_level_dir
            return self._strip_archive_suffix(archive_name), None

        if top_level_dir:
            return None, top_level_dir
        return None, None

    def _strip_archive_suffix(self, name: str) -> str:
        lower = name.lower()
        if lower.endswith(".tar.gz"):
            return name[:-7]
        if lower.endswith(".tgz"):
            return name[:-4]
        if lower.endswith(".tar"):
            return name[:-4]
        if lower.endswith(".zip"):
            return name[:-4]
        return name

    def _clean_archive_path(
        self,
        path_str: str,
        strip_prefix: str | None,
    ) -> PurePosixPath | None:
        rel_path = PurePosixPath(path_str.replace("\\", "/"))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            return None
        if not rel_path.parts:
            return None

        parts = list(rel_path.parts)
        if strip_prefix and parts and parts[0] == strip_prefix:
            parts = parts[1:]
        if not parts:
            return None
        return PurePosixPath(*parts)

    def _is_zip_symlink(self, info: zipfile.ZipInfo) -> bool:
        if info.create_system != 3:  # Not Unix
            return False
        return (info.external_attr >> 16) & 0o170000 == 0o120000
