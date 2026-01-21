"""
Management command to migrate legacy conversations and documents to default project/workspace.

This command finds all Conversation and Document records that don't have project/workspace
assignments and assigns them to the organization's default project and workspace.

Usage:
    python manage.py migrate_legacy_data
    python manage.py migrate_legacy_data --dry-run  # Preview without making changes
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from organizations.models import Organization

from chat.models import Conversation
from documents.models import Document, Collection
from projects.models import Project
from workspaces.models import Workspace

User = get_user_model()


class Command(BaseCommand):
    help = 'Migrate legacy conversations and documents to default project/workspace'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without actually updating the database',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')

        # Get all conversations without project/workspace
        conversations_to_migrate = Conversation.objects.filter(
            project__isnull=True
        ) | Conversation.objects.filter(
            workspace__isnull=True
        )

        # Get all documents without project/workspace
        documents_to_migrate = Document.objects.filter(
            project__isnull=True
        ) | Document.objects.filter(
            workspace__isnull=True
        )

        # Get all collections without project/workspace
        collections_to_migrate = Collection.objects.filter(
            project__isnull=True
        ) | Collection.objects.filter(
            workspace__isnull=True
        )

        total_conversations = conversations_to_migrate.count()
        total_documents = documents_to_migrate.count()
        total_collections = collections_to_migrate.count()

        self.stdout.write(self.style.HTTP_INFO('Migration Summary:'))
        self.stdout.write(f'  Conversations to migrate: {total_conversations}')
        self.stdout.write(f'  Documents to migrate: {total_documents}')
        self.stdout.write(f'  Collections to migrate: {total_collections}')
        self.stdout.write('')

        if total_conversations == 0 and total_documents == 0 and total_collections == 0:
            self.stdout.write(self.style.SUCCESS('✓ No data needs migration!'))
            return

        # Process each organization
        organizations = Organization.objects.all()

        migrated_conversations = 0
        migrated_documents = 0
        migrated_collections = 0

        for org in organizations:
            self.stdout.write(self.style.HTTP_INFO(f'Processing organization: {org.name}'))

            # Get default project for this organization
            default_project = Project.objects.filter(organization=org).first()

            if not default_project:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ No project found for {org.name}. Skipping this organization.'
                    )
                )
                continue

            # Get default workspace for the project
            default_workspace = Workspace.objects.filter(
                project=default_project,
                parent=None
            ).first()

            if not default_workspace:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ No workspace found for project {default_project.name}. '
                        f'Skipping this organization.'
                    )
                )
                continue

            self.stdout.write(f'  Using project: {default_project.name}')
            self.stdout.write(f'  Using workspace: {default_workspace.name}')

            # Migrate conversations for this organization
            org_conversations = conversations_to_migrate.filter(organization=org)
            conv_count = org_conversations.count()

            if conv_count > 0:
                self.stdout.write(f'  Migrating {conv_count} conversations...')
                if not dry_run:
                    org_conversations.update(
                        project=default_project,
                        workspace=default_workspace
                    )
                migrated_conversations += conv_count

            # Migrate documents for this organization
            org_documents = documents_to_migrate.filter(organization=org)
            doc_count = org_documents.count()

            if doc_count > 0:
                self.stdout.write(f'  Migrating {doc_count} documents...')
                if not dry_run:
                    org_documents.update(
                        project=default_project,
                        workspace=default_workspace
                    )
                migrated_documents += doc_count

            # Migrate collections for this organization
            org_collections = collections_to_migrate.filter(organization=org)
            coll_count = org_collections.count()

            if coll_count > 0:
                self.stdout.write(f'  Migrating {coll_count} collections...')
                if not dry_run:
                    org_collections.update(
                        project=default_project,
                        workspace=default_workspace
                    )
                migrated_collections += coll_count

            self.stdout.write('')

        # Display final summary
        self.stdout.write('=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ MIGRATION COMPLETE!'))
        self.stdout.write('=' * 60)
        self.stdout.write('')
        self.stdout.write(f'  Conversations migrated: {migrated_conversations}')
        self.stdout.write(f'  Documents migrated: {migrated_documents}')
        self.stdout.write(f'  Collections migrated: {migrated_collections}')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to apply these changes')
            )
