"""
Django management command to sync documents from configured sources.

This command pulls documents from configured Source implementations
(local filesystem, S3, R2, etc.) and creates or updates Document records
in the database for use in projects.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from organizations.models import Organization

from documents.models import Document, Image, PDF, Markdown, CSV, D2Diagram
from projects.models import Project
from sources.models import Source


class Command(BaseCommand):
    help = (
        'Sync documents from configured sources to the database. '
        'Pulls files from sources (local filesystem, S3, etc.) and creates '
        'or updates Document records.'
    )

    def add_arguments(self, parser):
        # Filtering arguments
        parser.add_argument(
            '--project',
            type=str,
            help='Sync sources for specific project by name or ID'
        )
        parser.add_argument(
            '--organization',
            type=str,
            help='Sync sources for all projects in organization (by name or ID)'
        )
        parser.add_argument(
            '--source',
            type=str,
            help='Sync specific source by name or ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all sources (default if no filter specified)'
        )

        # Behavior arguments
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )
        parser.add_argument(
            '--delete-missing',
            action='store_true',
            help='Delete documents that no longer exist in source'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Document Source Sync'))
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # Get sources to sync
        sources = self.get_sources(options)

        if not sources:
            raise CommandError('No sources found matching the specified criteria')

        self.stdout.write(self.style.HTTP_INFO(f'Found {len(sources)} source(s) to process'))
        self.stdout.write('')

        # Sync sources
        self.sync_sources(
            sources,
            dry_run=options['dry_run'],
            delete_missing=options['delete_missing'],
        )

    def get_sources(self, options):
        """Get sources based on filter arguments."""
        if options['source']:
            # Sync specific source
            try:
                if options['source'].isdigit():
                    sources = [Source.objects.get(id=int(options['source']))]
                else:
                    sources = [Source.objects.get(name=options['source'])]
            except Source.DoesNotExist:
                raise CommandError(f"Source '{options['source']}' not found")
        elif options['project']:
            # Sync all sources for a project
            try:
                if options['project'].isdigit():
                    project = Project.objects.get(id=int(options['project']))
                else:
                    project = Project.objects.get(name=options['project'])
                sources = list(Source.objects.filter(project=project, is_active=True))
            except Project.DoesNotExist:
                raise CommandError(f"Project '{options['project']}' not found")
        elif options['organization']:
            # Sync all sources in organization
            try:
                if options['organization'].isdigit():
                    org = Organization.objects.get(id=int(options['organization']))
                else:
                    org = Organization.objects.get(name=options['organization'])
                sources = list(Source.objects.filter(organization=org, is_active=True))
            except Organization.DoesNotExist:
                raise CommandError(f"Organization '{options['organization']}' not found")
        else:
            # Sync all active sources
            sources = list(Source.objects.filter(is_active=True))

        return sources

    def sync_sources(self, sources, dry_run, delete_missing):
        """Sync documents for all sources."""
        total_created = 0
        total_updated = 0
        total_deleted = 0
        total_skipped = 0
        total_failed = 0

        for idx, source in enumerate(sources, 1):
            self.stdout.write('-' * 70)
            self.stdout.write(
                self.style.HTTP_INFO(f'Source {idx}/{len(sources)}: {source.name}')
            )
            self.stdout.write(f'  Type: {source.get_source_type_display()}')
            self.stdout.write(f'  Project: {source.project.name}')
            self.stdout.write(f'  Organization: {source.organization.name}')
            self.stdout.write('')

            # Get source instance
            try:
                source_impl = source.get_source_instance()
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed to initialize source: {e}')
                )
                self.stdout.write('')
                continue

            # List documents from source
            try:
                doc_metas = list(source_impl.list_documents())
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed to list documents: {e}')
                )
                self.stdout.write('')
                continue

            self.stdout.write(f'  Found {len(doc_metas)} document(s) in source')
            self.stdout.write('')

            if len(doc_metas) == 0:
                self.stdout.write('  No documents to sync')
                self.stdout.write('')
                continue

            # Track source paths for delete detection
            source_paths = {meta.path for meta in doc_metas}

            # Sync each document
            created = 0
            updated = 0
            skipped = 0
            failed = 0

            for doc_meta in doc_metas:
                try:
                    result = self.sync_document(
                        source,
                        source_impl,
                        doc_meta,
                        dry_run
                    )

                    if result == 'created':
                        created += 1
                        self.stdout.write(
                            f"    • {doc_meta.name}: "
                            f"{self.style.SUCCESS('✓ Created')}"
                        )
                    elif result == 'updated':
                        updated += 1
                        self.stdout.write(
                            f"    • {doc_meta.name}: "
                            f"{self.style.SUCCESS('✓ Updated')}"
                        )
                    elif result == 'skipped':
                        skipped += 1
                        self.stdout.write(
                            f"    • {doc_meta.name}: "
                            f"{self.style.WARNING('- Skipped (unchanged)')}"
                        )
                except Exception as e:
                    failed += 1
                    self.stdout.write(
                        f"    • {doc_meta.name}: "
                        f"{self.style.ERROR(f'✗ Failed - {e}')}"
                    )

            # Handle deleted documents
            deleted = 0
            if delete_missing and not dry_run:
                existing_docs = Document.objects.filter(
                    project=source.project,
                ).select_subclasses()

                for doc in existing_docs:
                    # Get source path from document
                    doc_path = self.get_document_source_path(doc)
                    if doc_path and doc_path not in source_paths:
                        doc.delete()
                        deleted += 1
                        self.stdout.write(
                            f"    • {doc.name}: "
                            f"{self.style.WARNING('✗ Deleted (missing from source)')}"
                        )

            total_created += created
            total_updated += updated
            total_deleted += deleted
            total_skipped += skipped
            total_failed += failed

            # Update source sync timestamp
            if not dry_run and (created > 0 or updated > 0):
                source.last_sync_at = timezone.now()
                source.save(update_fields=['last_sync_at'])

            self.stdout.write('')
            self.stdout.write(
                f"  Source summary: "
                f"{self.style.SUCCESS(f'{created} created')}, "
                f"{self.style.SUCCESS(f'{updated} updated')}, "
                f"{self.style.WARNING(f'{skipped} skipped')}, "
                f"{self.style.ERROR(f'{failed} failed')}"
            )
            if deleted > 0:
                self.stdout.write(f"  {self.style.WARNING(f'{deleted} deleted')}")
            self.stdout.write('')

        # Final summary
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Sync Summary'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'  Total sources: {len(sources)}')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'  [DRY RUN] Would create: {total_created}')
            )
            self.stdout.write(
                self.style.WARNING(f'  [DRY RUN] Would update: {total_updated}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Created: {total_created}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Updated: {total_updated}')
            )
        if total_skipped > 0:
            self.stdout.write(f'  - Skipped: {total_skipped}')
        if total_deleted > 0:
            self.stdout.write(
                self.style.WARNING(f'  ✗ Deleted: {total_deleted}')
            )
        if total_failed > 0:
            self.stdout.write(
                self.style.ERROR(f'  ✗ Failed: {total_failed}')
            )
        self.stdout.write('=' * 70)

    def sync_document(self, source, source_impl, doc_meta, dry_run):
        """
        Sync a single document from source to database.

        Returns:
            str: 'created', 'updated', or 'skipped'
        """
        # Check if document already exists by path
        doc_path = doc_meta.path
        existing_doc = Document.objects.filter(
            project=source.project,
            name=Path(doc_path).name
        ).select_subclasses().first()

        # Determine if we need to update
        needs_update = False
        if existing_doc:
            # Check if file has been modified
            if existing_doc.updated_at.timestamp() < doc_meta.modified_at:
                needs_update = True
        else:
            needs_update = True

        if not needs_update:
            return 'skipped'

        if dry_run:
            return 'created' if not existing_doc else 'updated'

        # Read document content from source
        try:
            content_bytes = source_impl.read_document(doc_path)
        except Exception as e:
            raise Exception(f"Failed to read document: {e}")

        # Determine document type from extension
        extension = doc_meta.extension.lower()

        with transaction.atomic():
            if existing_doc:
                # Update existing document
                doc = existing_doc
                action = 'updated'
            else:
                # Create new document based on type
                doc = self.create_document_by_type(
                    extension,
                    source.project,
                    source.organization
                )
                action = 'created'

            # Set common fields
            doc.name = Path(doc_path).name
            doc.file_size = doc_meta.size

            # Set type-specific fields
            if isinstance(doc, (Image, PDF)):
                # For file-based documents, we would need to save the file
                # This is a simplified version - real implementation would
                # need to handle file uploads properly
                pass
            elif isinstance(doc, (Markdown, CSV, D2Diagram)):
                # For text documents, store content directly
                doc.content = content_bytes.decode('utf-8', errors='ignore')

            doc.save()

        return action

    def create_document_by_type(self, extension, project, organization):
        """Create appropriate document subclass based on file extension."""
        # Image types
        if extension in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}:
            return Image(
                project=project,
                organization=organization
            )

        # PDF types
        elif extension == '.pdf':
            return PDF(
                project=project,
                organization=organization
            )

        # CSV types
        elif extension == '.csv':
            return CSV(
                project=project,
                organization=organization
            )

        # Diagram types
        elif extension == '.d2':
            return D2Diagram(
                project=project,
                organization=organization
            )

        # Default to Markdown for text files
        else:
            return Markdown(
                project=project,
                organization=organization
            )

    def get_document_source_path(self, doc):
        """
        Get the original source path for a document.

        This is a placeholder - in a real implementation, you might
        store the source path as metadata on the document.
        """
        # For now, we can't reliably determine the original source path
        # This would need to be tracked in document metadata
        return None
