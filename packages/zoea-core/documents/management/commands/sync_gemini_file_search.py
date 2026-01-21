"""
Django management command to sync Project documents to the file search store.

Creates a File Search store per Project and uploads documents for semantic
search and RAG capabilities.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.utils import timezone
from organizations.models import Organization

from file_search import FileSearchRegistry
from file_search.indexing import ensure_project_store, index_document
from documents.models import Document
from projects.models import Project


class Command(BaseCommand):
    help = (
        'Sync Project documents to File Search stores. '
        'Creates a File Search store per project and uploads all documents '
        'with metadata for filtering and citations.'
    )

    def add_arguments(self, parser):
        # Filtering arguments
        parser.add_argument(
            '--project',
            type=str,
            help='Sync specific project by name or ID'
        )
        parser.add_argument(
            '--organization',
            type=str,
            help='Sync all projects in organization (by name or ID)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Sync all projects (default if no filter specified)'
        )

        # Source sync integration
        parser.add_argument(
            '--sync-sources',
            action='store_true',
            help='First sync documents from sources before uploading to File Search'
        )

        # Behavior arguments
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync all documents even if already synced'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )
        parser.add_argument(
            '--delete-store',
            action='store_true',
            help='Delete File Search store for project(s)'
        )

        # Chunking configuration
        parser.add_argument(
            '--max-tokens-per-chunk',
            type=int,
            default=200,
            help='Maximum tokens per chunk for document splitting (default: 200)'
        )
        parser.add_argument(
            '--max-overlap-tokens',
            type=int,
            default=20,
            help='Maximum overlapping tokens between chunks (default: 20)'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('File Search Sync'))
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # Sync from sources first if requested
        if options['sync_sources']:
            self.stdout.write(self.style.HTTP_INFO('Step 1: Syncing documents from sources'))
            self.stdout.write('-' * 70)
            self.stdout.write('')

            from sources.models import Source

            # Get sources based on filter
            if options['project']:
                try:
                    if options['project'].isdigit():
                        project = Project.objects.get(id=int(options['project']))
                    else:
                        project = Project.objects.get(name=options['project'])
                    sources = Source.objects.filter(project=project, is_active=True)
                except Project.DoesNotExist:
                    raise CommandError(f"Project '{options['project']}' not found")
            elif options['organization']:
                try:
                    if options['organization'].isdigit():
                        org = Organization.objects.get(id=int(options['organization']))
                    else:
                        org = Organization.objects.get(name=options['organization'])
                    sources = Source.objects.filter(organization=org, is_active=True)
                except Organization.DoesNotExist:
                    raise CommandError(f"Organization '{options['organization']}' not found")
            else:
                sources = Source.objects.filter(is_active=True)

            source_count = sources.count()
            if source_count > 0:
                self.stdout.write(f'Found {source_count} active source(s) to sync')
                self.stdout.write('Running sync_sources command...')
                self.stdout.write('')

                # Call sync_sources command
                from django.core.management import call_command
                call_command(
                    'sync_sources',
                    project=options.get('project'),
                    organization=options.get('organization'),
                    dry_run=options['dry_run']
                )

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('✓ Source sync complete'))
                self.stdout.write('')
                self.stdout.write('=' * 70)
                self.stdout.write(self.style.HTTP_INFO('Step 2: Uploading to File Search'))
                self.stdout.write('=' * 70)
                self.stdout.write('')
            else:
                self.stdout.write(self.style.WARNING('No active sources found - skipping source sync'))
                self.stdout.write('')

        # Initialize backend
        try:
            self.store = FileSearchRegistry.get()
        except Exception as e:
            raise CommandError(str(e))

        # Get projects to sync
        projects = self.get_projects(options)

        if not projects:
            raise CommandError('No projects found matching the specified criteria')

        self.stdout.write(self.style.HTTP_INFO(f'Found {len(projects)} project(s) to process'))
        self.stdout.write('')

        # Handle delete-store action
        if options['delete_store']:
            self.delete_stores(projects, options['dry_run'])
            return

        # Sync projects
        self.sync_projects(
            projects,
            force=options['force'],
            dry_run=options['dry_run'],
            max_tokens_per_chunk=options['max_tokens_per_chunk'],
            max_overlap_tokens=options['max_overlap_tokens']
        )

    def get_projects(self, options):
        """Get projects based on filter arguments."""
        if options['project']:
            # Sync specific project
            try:
                # Try by ID first
                if options['project'].isdigit():
                    projects = [Project.objects.get(id=int(options['project']))]
                else:
                    # Try by name
                    projects = [Project.objects.get(name=options['project'])]
            except Project.DoesNotExist:
                raise CommandError(f"Project '{options['project']}' not found")
        elif options['organization']:
            # Sync all projects in organization
            try:
                # Try by ID first
                if options['organization'].isdigit():
                    org = Organization.objects.get(id=int(options['organization']))
                else:
                    # Try by name
                    org = Organization.objects.get(name=options['organization'])
                projects = list(Project.objects.filter(organization=org))
            except Organization.DoesNotExist:
                raise CommandError(f"Organization '{options['organization']}' not found")
        else:
            # Sync all projects (default)
            projects = list(Project.objects.all())

        return projects

    def delete_stores(self, projects, dry_run):
        """Delete File Search stores for projects."""
        self.stdout.write(self.style.WARNING('Deleting File Search stores...'))
        self.stdout.write('')

        deleted_count = 0
        for project in projects:
            if not project.gemini_store_id:
                self.stdout.write(
                    f"  • {project.name}: "
                    f"{self.style.WARNING('No store to delete')}"
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  • {project.name}: "
                    f"{self.style.WARNING('[DRY RUN]')} Would delete store"
                )
            else:
                try:
                    self.store.delete_store(project.gemini_store_id)
                    project.gemini_store_id = None
                    project.gemini_store_name = None
                    project.gemini_synced_at = None
                    project.save(
                        update_fields=['gemini_store_id', 'gemini_store_name', 'gemini_synced_at']
                    )

                    # Clear document sync status
                    Document.objects.filter(project=project).update(
                        gemini_file_id=None,
                        gemini_synced_at=None
                    )

                    self.stdout.write(
                        f"  • {project.name}: "
                        f"{self.style.SUCCESS('✓ Deleted')}"
                    )
                    deleted_count += 1
                except Exception as e:
                    self.stdout.write(
                        f"  • {project.name}: "
                        f"{self.style.ERROR('✗ Failed')} - {e}"
                    )

        self.stdout.write('')
        self.stdout.write('-' * 70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Would delete {len([p for p in projects if p.gemini_store_id])} store(s)'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Deleted {deleted_count} store(s)')
            )
        self.stdout.write('=' * 70)

    def sync_projects(self, projects, force, dry_run, max_tokens_per_chunk, max_overlap_tokens):
        """Sync documents for all projects."""
        total_docs = 0
        total_synced = 0
        total_skipped = 0
        total_failed = 0

        for idx, project in enumerate(projects, 1):
            self.stdout.write('-' * 70)
            self.stdout.write(
                self.style.HTTP_INFO(f'Project {idx}/{len(projects)}: {project.name}')
            )
            self.stdout.write(f'  Organization: {project.organization.name}')
            self.stdout.write('')

            # Create or get File Search store
            if dry_run:
                self.stdout.write(
                    f"  {self.style.WARNING('[DRY RUN]')} Would create/get File Search store"
                )
                store_info = {'name': 'dry-run-store', 'display_name': 'Dry Run'}
            else:
                try:
                    store_info = ensure_project_store(project)
                    self.stdout.write(
                        f"  {self.style.SUCCESS('✓')} File Search store: {store_info.display_name}"
                    )
                except Exception as e:
                    self.stdout.write(
                        f"  {self.style.ERROR('✗ Failed to create/get store')}: {e}"
                    )
                    continue

            self.stdout.write('')

            # Get documents to sync
            documents = Document.objects.filter(project=project).select_subclasses()

            if not force:
                # Incremental sync - only unsynced or modified documents
                documents = documents.filter(
                    models.Q(gemini_file_id__isnull=True) |
                    models.Q(gemini_synced_at__isnull=True) |
                    models.Q(updated_at__gt=models.F('gemini_synced_at'))
                )

            doc_count = documents.count()
            total_docs += doc_count

            if doc_count == 0:
                self.stdout.write(f"  {self.style.WARNING('No documents to sync')}")
                self.stdout.write('')
                continue

            self.stdout.write(f"  Syncing {doc_count} document(s)...")
            self.stdout.write('')

            # Upload each document
            synced = 0
            skipped = 0
            failed = 0

            for doc in documents:
                doc_type = doc.get_type_name()

                if dry_run:
                    self.stdout.write(
                        f"    • {doc.name} ({doc_type}): "
                        f"{self.style.WARNING('[DRY RUN]')} Would upload"
                    )
                    synced += 1
                else:
                    try:
                        index_document(doc, force=force)

                        self.stdout.write(
                            f"    • {doc.name} ({doc_type}): "
                            f"{self.style.SUCCESS('✓ Synced')}"
                        )
                        synced += 1
                    except Exception as e:
                        self.stdout.write(
                            f"    • {doc.name} ({doc_type}): "
                            f"{self.style.ERROR('✗ Failed')} - {e}"
                        )
                        failed += 1

            total_synced += synced
            total_skipped += skipped
            total_failed += failed

            # Update project sync timestamp
            if not dry_run and synced > 0:
                project.gemini_synced_at = timezone.now()
                project.save(update_fields=['gemini_synced_at'])

            self.stdout.write('')
            self.stdout.write(
                f"  Project summary: "
                f"{self.style.SUCCESS(f'{synced} synced')}, "
                f"{self.style.ERROR(f'{failed} failed')}"
            )
            self.stdout.write('')

        # Final summary
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Sync Summary'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'  Total projects: {len(projects)}')
        self.stdout.write(f'  Total documents: {total_docs}')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'  [DRY RUN] Would sync: {total_synced}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Synced: {total_synced}')
            )
        if total_failed > 0:
            self.stdout.write(
                self.style.ERROR(f'  ✗ Failed: {total_failed}')
            )
        self.stdout.write('=' * 70)
