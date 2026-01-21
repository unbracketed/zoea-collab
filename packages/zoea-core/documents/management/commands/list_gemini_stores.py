"""
Django management command to list all Gemini File Search stores.

This command displays all File Search stores associated with the account,
showing store details and matching them with Projects where possible.
"""

from django.core.management.base import BaseCommand, CommandError

from documents.gemini_service import GeminiFileSearchService
from projects.models import Project


class Command(BaseCommand):
    help = 'List all Gemini File Search stores and their associated projects'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed store information'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Gemini File Search Stores'))
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # Initialize service
        try:
            service = GeminiFileSearchService()
        except ValueError as e:
            raise CommandError(str(e))

        # Get all stores
        try:
            stores = list(service.list_stores())
        except Exception as e:
            raise CommandError(f"Failed to list stores: {e}")

        if not stores:
            self.stdout.write(self.style.WARNING('No File Search stores found'))
            self.stdout.write('')
            self.stdout.write('=' * 70)
            return

        self.stdout.write(self.style.HTTP_INFO(f'Found {len(stores)} store(s)'))
        self.stdout.write('')

        # Get all projects with store IDs for matching
        project_map = {}
        for project in Project.objects.filter(gemini_store_id__isnull=False):
            project_map[project.gemini_store_id] = project

        # Display each store
        for idx, store in enumerate(stores, 1):
            self.stdout.write('-' * 70)
            self.stdout.write(self.style.HTTP_INFO(f'Store {idx}'))
            self.stdout.write('')

            # Basic information
            self.stdout.write(f"  Name: {self.style.SUCCESS(store.name)}")

            if hasattr(store, 'display_name') and store.display_name:
                self.stdout.write(f"  Display Name: {store.display_name}")

            # Match with project if exists
            if store.name in project_map:
                project = project_map[store.name]
                self.stdout.write(
                    f"  Project: {self.style.SUCCESS(project.name)} "
                    f"(Organization: {project.organization.name})"
                )
                if project.gemini_synced_at:
                    self.stdout.write(
                        f"  Last Synced: {project.gemini_synced_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            else:
                self.stdout.write(
                    f"  Project: {self.style.WARNING('Not matched to any project')}"
                )

            # Verbose information
            if options['verbose']:
                self.stdout.write('')
                self.stdout.write('  Additional Details:')

                if hasattr(store, 'create_time') and store.create_time:
                    self.stdout.write(f"    Created: {store.create_time}")

                if hasattr(store, 'update_time') and store.update_time:
                    self.stdout.write(f"    Updated: {store.update_time}")

                # Display all available attributes
                excluded_attrs = ['name', 'display_name', 'create_time', 'update_time']
                for attr in dir(store):
                    if not attr.startswith('_') and attr not in excluded_attrs:
                        value = getattr(store, attr, None)
                        if value and not callable(value):
                            self.stdout.write(f"    {attr}: {value}")

            self.stdout.write('')

        # Summary
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.HTTP_INFO('Summary'))
        self.stdout.write('=' * 70)

        matched_count = sum(1 for store in stores if store.name in project_map)
        unmatched_count = len(stores) - matched_count

        self.stdout.write(f'  Total stores: {len(stores)}')
        self.stdout.write(f'  Matched to projects: {self.style.SUCCESS(str(matched_count))}')

        if unmatched_count > 0:
            self.stdout.write(
                f'  Unmatched (orphaned): {self.style.WARNING(str(unmatched_count))}'
            )
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    '  Note: Orphaned stores may have been created for deleted projects.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '  Use "sync_gemini_file_search --delete-store" to clean them up.'
                )
            )

        self.stdout.write('=' * 70)
