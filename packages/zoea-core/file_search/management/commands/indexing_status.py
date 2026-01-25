"""
Django management command to show file search indexing status.

Displays pending and failed indexing tasks, documents with sync errors,
and overall indexing health metrics.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Show file search indexing status including pending tasks, "
        "failed documents, and overall sync health."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=str,
            help="Filter by project name or ID",
        )
        parser.add_argument(
            "--errors-only",
            action="store_true",
            help="Only show documents with sync errors",
        )
        parser.add_argument(
            "--pending-only",
            action="store_true",
            help="Only show pending/queued tasks",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of items to display per section (default: 20)",
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.HTTP_INFO("File Search Indexing Status"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

        project = None
        if options["project"]:
            from projects.models import Project

            try:
                if options["project"].isdigit():
                    project = Project.objects.get(id=int(options["project"]))
                else:
                    project = Project.objects.get(name=options["project"])
                self.stdout.write(f"Filtering by project: {project.name}")
                self.stdout.write("")
            except Project.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Project '{options['project']}' not found")
                )
                return

        if not options["errors_only"]:
            self.show_queue_status(options["limit"])
            self.stdout.write("")

        if not options["pending_only"]:
            self.show_document_sync_status(project, options["limit"])
            self.stdout.write("")
            self.show_platform_message_status(project, options["limit"])
            self.stdout.write("")
            self.show_documents_with_errors(project, options["limit"])

        self.stdout.write("=" * 70)

    def show_queue_status(self, limit):
        """Show Django-Q2 task queue status for indexing tasks."""
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.HTTP_INFO("Background Task Queue"))
        self.stdout.write("-" * 70)

        try:
            from django_q.models import OrmQ, Success, Failure

            # Total pending tasks (OrmQ stores task data in payload blob)
            total_pending = OrmQ.objects.count()
            self.stdout.write(f"\nTotal Pending Tasks: {total_pending}")

            # Recent successes - filter by task name patterns
            recent_success = Success.objects.filter(
                Q(name__icontains="index_document") |
                Q(name__icontains="index_chat") |
                Q(name__icontains="index_email") |
                Q(name__icontains="reindex_project") |
                Q(func__icontains="file_search.tasks")
            ).order_by("-stopped")[:5]

            if recent_success.exists():
                self.stdout.write(f"\nRecent Successful Indexing Tasks:")
                for task in recent_success:
                    elapsed = task.stopped - task.started if task.stopped and task.started else None
                    elapsed_str = f"{elapsed.total_seconds():.1f}s" if elapsed else "N/A"
                    self.stdout.write(
                        f"  {self.style.SUCCESS('+')} {task.name or task.func} "
                        f"({elapsed_str})"
                    )

            # Recent failures - filter by task name patterns
            recent_failures = Failure.objects.filter(
                Q(name__icontains="index_document") |
                Q(name__icontains="index_chat") |
                Q(name__icontains="index_email") |
                Q(name__icontains="reindex_project") |
                Q(func__icontains="file_search.tasks")
            ).order_by("-stopped")[:limit]

            if recent_failures.exists():
                self.stdout.write(
                    f"\n{self.style.ERROR('Failed Indexing Tasks:')} {recent_failures.count()}"
                )
                for task in recent_failures:
                    error = str(task.result or "Unknown error")[:100]
                    self.stdout.write(
                        f"  {self.style.ERROR('x')} {task.name or task.func}: {error}"
                    )

        except ImportError:
            self.stdout.write(
                self.style.WARNING("Django-Q2 not available - skipping queue status")
            )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Could not fetch queue status: {e}")
            )

    def show_document_sync_status(self, project, limit):
        """Show document synchronization status summary."""
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.HTTP_INFO("Document Sync Status"))
        self.stdout.write("-" * 70)

        from documents.models import Document

        queryset = Document.objects.all()
        if project:
            queryset = queryset.filter(project=project)

        # Overall counts
        total = queryset.count()
        synced = queryset.filter(gemini_synced_at__isnull=False).count()
        not_synced = queryset.filter(gemini_synced_at__isnull=True).count()
        with_errors = queryset.filter(gemini_sync_error__isnull=False).exclude(
            gemini_sync_error=""
        ).count()

        self.stdout.write(f"\nTotal Documents: {total}")
        self.stdout.write(f"  {self.style.SUCCESS('Synced:')} {synced}")
        self.stdout.write(f"  Not Synced: {not_synced}")
        if with_errors > 0:
            self.stdout.write(f"  {self.style.ERROR('With Errors:')} {with_errors}")

        # Sync percentage
        if total > 0:
            sync_pct = (synced / total) * 100
            if sync_pct >= 90:
                style = self.style.SUCCESS
            elif sync_pct >= 70:
                style = self.style.WARNING
            else:
                style = self.style.ERROR
            self.stdout.write(f"\n  Sync Rate: {style(f'{sync_pct:.1f}%')}")

        # Documents never synced (excluding recent ones)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        never_synced = queryset.filter(
            gemini_synced_at__isnull=True,
            created_at__lt=one_hour_ago,
        ).select_subclasses()[:limit]

        if never_synced:
            self.stdout.write(f"\nDocuments Never Synced (older than 1 hour):")
            for doc in never_synced:
                doc_type = doc.get_type_name()
                self.stdout.write(
                    f"  - [{doc.id}] {doc.name[:40]} ({doc_type})"
                )

    def show_platform_message_status(self, project, limit):
        """Show platform message indexing status."""
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.HTTP_INFO("Platform Message Status"))
        self.stdout.write("-" * 70)

        from platform_adapters.models import MessageStatus, PlatformMessage

        queryset = PlatformMessage.objects.all()
        if project:
            queryset = queryset.filter(project=project)

        # Overall counts
        total = queryset.count()
        processing = queryset.filter(status=MessageStatus.PROCESSING).count()
        processed = queryset.filter(status=MessageStatus.PROCESSED).count()
        failed = queryset.filter(status=MessageStatus.FAILED).count()
        ignored = queryset.filter(status=MessageStatus.IGNORED).count()
        with_project = queryset.filter(project__isnull=False).count()

        self.stdout.write(f"\nTotal Platform Messages: {total}")
        self.stdout.write(f"  Processing: {processing}")
        self.stdout.write(f"  Processed: {processed}")
        if failed > 0:
            self.stdout.write(f"  {self.style.ERROR('Failed:')} {failed}")
        self.stdout.write(f"  Ignored: {ignored}")
        self.stdout.write(f"  With Project (indexable): {with_project}")

        # Recent messages without project (can't be indexed)
        no_project = queryset.filter(
            project__isnull=True,
            status=MessageStatus.PROCESSING,
        ).select_related("connection")[:limit]

        if no_project.exists():
            self.stdout.write(
                f"\n{self.style.WARNING('Messages without project (not indexed):')}"
            )
            for msg in no_project:
                self.stdout.write(
                    f"  - [{msg.id}] {msg.connection.name}: "
                    f"{msg.content[:40]}..."
                )

    def show_documents_with_errors(self, project, limit):
        """Show documents that have sync errors."""
        self.stdout.write("-" * 70)
        self.stdout.write(self.style.HTTP_INFO("Documents with Sync Errors"))
        self.stdout.write("-" * 70)

        from documents.models import Document

        queryset = Document.objects.filter(
            gemini_sync_error__isnull=False
        ).exclude(gemini_sync_error="")

        if project:
            queryset = queryset.filter(project=project)

        error_docs = queryset.select_subclasses().order_by("-gemini_sync_attempts")[:limit]

        if not error_docs:
            self.stdout.write(self.style.SUCCESS("\nNo documents with sync errors!"))
            return

        self.stdout.write(f"\nFound {queryset.count()} documents with errors:")

        for doc in error_docs:
            doc_type = doc.get_type_name()
            attempts = getattr(doc, "gemini_sync_attempts", 0)
            error = (doc.gemini_sync_error or "")[:60]
            self.stdout.write(
                f"\n  {self.style.ERROR('x')} [{doc.id}] {doc.name[:30]} ({doc_type})"
            )
            self.stdout.write(f"      Attempts: {attempts}")
            self.stdout.write(f"      Error: {error}...")

        # Aggregate errors by type
        self.stdout.write("\nError Summary by Document Type:")
        error_by_type = (
            queryset.values("textdocument__isnull", "pdf__isnull", "image__isnull")
            .annotate(count=Count("id"))
        )

        # Simpler approach - just count by filtering
        from documents.models import Image, PDF, TextDocument

        image_errors = queryset.filter(id__in=Image.objects.values("document_ptr_id")).count()
        pdf_errors = queryset.filter(id__in=PDF.objects.values("document_ptr_id")).count()
        text_errors = queryset.filter(id__in=TextDocument.objects.values("document_ptr_id")).count()
        other_errors = queryset.count() - image_errors - pdf_errors - text_errors

        if image_errors:
            self.stdout.write(f"  Image: {image_errors}")
        if pdf_errors:
            self.stdout.write(f"  PDF: {pdf_errors}")
        if text_errors:
            self.stdout.write(f"  Text: {text_errors}")
        if other_errors:
            self.stdout.write(f"  Other: {other_errors}")
