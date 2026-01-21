"""
Django management command to reindex documents in the file search store.

This command re-indexes all documents for a project, ensuring that newly
supported document types (like Word and Excel) are properly searchable.
"""

from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from file_search.indexing import ensure_project_store, index_document
from projects.models import Project


class Command(BaseCommand):
    help = (
        "Reindex documents in the file search store. "
        "Use this after adding support for new document types or to refresh "
        "the search index for a project."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Project name or ID to reindex (required unless --all is specified)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Reindex all projects",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force reindex even if document appears up-to-date",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )
        parser.add_argument(
            "--type",
            type=str,
            help="Only reindex specific document type (e.g., WordDocument, SpreadsheetDocument)",
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.HTTP_INFO("Document Reindexing"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

        # Get projects to reindex
        projects = self.get_projects(options)

        if not projects:
            raise CommandError("No projects found. Use --project or --all.")

        self.stdout.write(
            self.style.HTTP_INFO(f"Found {len(projects)} project(s) to process")
        )
        self.stdout.write("")

        total_indexed = 0
        total_skipped = 0
        total_failed = 0

        for project in projects:
            indexed, skipped, failed = self.reindex_project(
                project,
                force=options["force"],
                dry_run=options["dry_run"],
                type_filter=options.get("type"),
            )
            total_indexed += indexed
            total_skipped += skipped
            total_failed += failed

        # Final summary
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.HTTP_INFO("Reindex Summary"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Total projects: {len(projects)}")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"  [DRY RUN] Would index: {total_indexed}")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"  Indexed: {total_indexed}"))

        if total_skipped > 0:
            self.stdout.write(f"  Skipped: {total_skipped}")
        if total_failed > 0:
            self.stdout.write(self.style.ERROR(f"  Failed: {total_failed}"))

        self.stdout.write("=" * 70)

    def get_projects(self, options):
        """Get projects based on filter arguments."""
        if options["project"]:
            try:
                if options["project"].isdigit():
                    return [Project.objects.get(id=int(options["project"]))]
                else:
                    return [Project.objects.get(name=options["project"])]
            except Project.DoesNotExist:
                raise CommandError(f"Project '{options['project']}' not found")
        elif options["all"]:
            return list(Project.objects.all())
        else:
            return []

    def reindex_project(self, project, force=False, dry_run=False, type_filter=None):
        """Reindex all documents for a project."""
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.HTTP_INFO(f"Project: {project.name} (ID: {project.id})"))

        # Ensure project has a file search store
        if not dry_run:
            try:
                store_info = ensure_project_store(project)
                self.stdout.write(f"  Store: {store_info.display_name}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Failed to ensure store: {e}"))
                return 0, 0, 0
        else:
            store_id = project.gemini_store_id
            if store_id:
                self.stdout.write(f"  Store: {store_id}")
            else:
                self.stdout.write(self.style.WARNING("  No store configured (will create)"))

        # Get documents to reindex
        documents = Document.objects.filter(project=project).select_subclasses()

        if type_filter:
            # Filter by document type
            documents = [
                doc for doc in documents if doc.get_type_name() == type_filter
            ]
            self.stdout.write(f"  Filtering by type: {type_filter}")

        doc_count = len(list(documents))
        self.stdout.write(f"  Documents to process: {doc_count}")
        self.stdout.write("")

        if doc_count == 0:
            self.stdout.write("  No documents to reindex")
            return 0, 0, 0

        indexed = 0
        skipped = 0
        failed = 0

        # Re-query to avoid generator exhaustion
        documents = Document.objects.filter(project=project).select_subclasses()
        if type_filter:
            documents = [
                doc for doc in documents if doc.get_type_name() == type_filter
            ]

        for doc in documents:
            doc_type = doc.get_type_name()
            try:
                if dry_run:
                    self.stdout.write(
                        f"    {self.style.SUCCESS('+')} {doc.name} ({doc_type})"
                    )
                    indexed += 1
                else:
                    index_document(doc, force=force)
                    self.stdout.write(
                        f"    {self.style.SUCCESS('+')} {doc.name} ({doc_type})"
                    )
                    indexed += 1
            except Exception as e:
                self.stdout.write(
                    f"    {self.style.ERROR('x')} {doc.name} ({doc_type}): {e}"
                )
                failed += 1

        self.stdout.write("")
        self.stdout.write(
            f"  Project summary: "
            f"{self.style.SUCCESS(f'{indexed} indexed')}, "
            f"{skipped} skipped, "
            f"{self.style.ERROR(f'{failed} failed')}"
        )
        self.stdout.write("")

        return indexed, skipped, failed
