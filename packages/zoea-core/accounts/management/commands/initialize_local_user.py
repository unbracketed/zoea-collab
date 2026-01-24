"""
Management command to initialize a local user with full setup.

This command creates or uses an existing user, creates an organization,
and automatically sets up the default project. Perfect for
local development and initial setup.

The command will:
1. Create a new user or use an existing one
2. Create an organization and make the user the owner
3. Automatically create a default project (via signals)
4. Optionally load demo documents from the demo-docs directory

Usage:
    # Create a new user with all defaults
    python manage.py initialize_local_user

    # Use specific username and org name
    python manage.py initialize_local_user --username brian --org-name "Citrus Grove"

    # Use existing user by email
    python manage.py initialize_local_user --email brian@example.com --org-name "My Company"

    # Create user with all options
    python manage.py initialize_local_user \\
        --username brian \\
        --email brian@example.com \\
        --password mypassword \\
        --org-name "Citrus Grove" \\
        --subscription pro \\
        --max-users 10

    # Load demo documents for a complete getting started experience
    python manage.py initialize_local_user --demo-docs
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from organizations.models import OrganizationOwner, OrganizationUser

from accounts.models import Account
from documents.models import D2Diagram, Folder, Markdown
from projects.models import Project

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialize a local user with organization and project'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the user (default: admin)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the user (default: admin@localhost)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the user (default: admin)',
        )
        parser.add_argument(
            '--org-name',
            type=str,
            help='Name of the organization to create',
        )
        parser.add_argument(
            '--subscription',
            type=str,
            default='free',
            choices=['free', 'pro', 'enterprise'],
            help='Subscription plan for the organization (default: free)',
        )
        parser.add_argument(
            '--max-users',
            type=int,
            default=5,
            help='Maximum number of users allowed (default: 5)',
        )
        parser.add_argument(
            '--use-existing',
            action='store_true',
            help='Use existing user if found instead of raising error',
        )
        parser.add_argument(
            '--demo-docs',
            action='store_true',
            help='Load demo documents from the demo-docs directory',
        )
        parser.add_argument(
            '--demo-docs-path',
            type=str,
            help='Custom path to demo documents directory (default: demo-docs in project root)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts (for non-interactive use)',
        )

    def handle(self, *args, **options):
        # Default values for local development
        username = options.get('username') or 'admin'
        email = options.get('email') or 'admin@localhost'
        password = options.get('password') or 'admin'
        use_existing = options.get('use_existing', False)

        # Step 1: Create or get user
        self.stdout.write(self.style.HTTP_INFO('Step 1: User Setup'))
        self.stdout.write('-' * 60)

        user, created = self._get_or_create_user(username, email, password, use_existing)

        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created new user: {user.username}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Using existing user: {user.username}'))

        # Check if user already has an organization
        existing_orgs = OrganizationUser.objects.filter(user=user)
        if existing_orgs.exists():
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    f'User {user.username} already belongs to {existing_orgs.count()} organization(s):'
                )
            )
            for org_user in existing_orgs:
                org = org_user.organization
                projects = Project.objects.filter(organization=org)
                self.stdout.write(f'  - {org.name}')
                self.stdout.write(f'    Projects: {projects.count()}')

            self.stdout.write('')

            # In force mode, skip creating another organization
            if options.get('force'):
                self.stdout.write(
                    self.style.SUCCESS('User already has an organization - skipping (--force mode)')
                )
                return

            confirm = input('Do you want to create another organization for this user? [y/N] ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Cancelled'))
                return

        # Step 2: Create organization
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('Step 2: Organization Setup'))
        self.stdout.write('-' * 60)

        org_name = options.get('org_name')
        if not org_name:
            # Default to user's name or username
            if user.get_full_name():
                org_name = f"{user.get_full_name()}'s Organization"
            else:
                org_name = f"{user.username}'s Organization"

        account = self._create_organization(user, org_name, options)
        self.stdout.write(self.style.SUCCESS(f'✓ Created organization: {account.name}'))

        # Step 3: Add user to organization (this triggers signals for Project and Workspace)
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('Step 3: Adding User to Organization'))
        self.stdout.write('-' * 60)

        org_user = self._add_user_to_organization(account, user)
        self.stdout.write(self.style.SUCCESS(f'✓ Added {user.username} as admin member'))

        # Step 4: Make user the owner
        self._make_user_owner(account, org_user)
        self.stdout.write(self.style.SUCCESS(f'✓ Made {user.username} the organization owner'))

        # Step 5: Verify project was created by signals
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('Step 4: Verifying Project'))
        self.stdout.write('-' * 60)

        project = self._verify_project(account)

        # Step 6: Load demo documents if requested
        folders_created = 0
        docs_created = 0
        if options.get('demo_docs') and project:
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('Step 5: Loading Demo Documents'))
            self.stdout.write('-' * 60)

            demo_docs_path = options.get('demo_docs_path')
            folders_created, docs_created = self._load_demo_docs(
                project, user, demo_docs_path
            )

            if folders_created or docs_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Loaded {docs_created} documents in {folders_created} folders'
                    )
                )
            else:
                self.stdout.write(self.style.WARNING('No demo documents were loaded'))

        # Display comprehensive summary
        self._display_summary(user, account, project, folders_created, docs_created)

    def _get_or_create_user(self, username, email, password, use_existing):
        """Get or create a user."""
        try:
            user = User.objects.get(username=username)
            if not use_existing:
                raise CommandError(
                    f'User "{username}" already exists. Use --use-existing to use this user, '
                    f'or choose a different username.'
                )
            return user, False
        except User.DoesNotExist:
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                return user, True
            except Exception as e:
                raise CommandError(f'Error creating user: {str(e)}')

    def _create_organization(self, user, org_name, options):
        """Create an organization."""
        try:
            account = Account.objects.create(
                name=org_name,
                subscription_plan=options['subscription'],
                max_users=options['max_users'],
                billing_email=user.email,
            )
            return account
        except Exception as e:
            raise CommandError(f'Error creating organization: {str(e)}')

    def _add_user_to_organization(self, account, user):
        """Add user to organization as admin."""
        try:
            org_user = OrganizationUser.objects.create(
                organization=account,
                user=user,
                is_admin=True,
            )
            return org_user
        except Exception as e:
            account.delete()
            raise CommandError(f'Error creating organization user: {str(e)}')

    def _make_user_owner(self, account, org_user):
        """Make user the organization owner."""
        try:
            OrganizationOwner.objects.create(
                organization=account,
                organization_user=org_user,
            )
        except Exception as e:
            org_user.delete()
            account.delete()
            raise CommandError(f'Error creating organization owner: {str(e)}')

    def _verify_project(self, account):
        """Verify that the default project was created by signals."""
        # Get the project created by the signal
        projects = Project.objects.filter(organization=account)

        if not projects.exists():
            self.stdout.write(
                self.style.ERROR('✗ No project was created! Check that signals are working.')
            )
            return None

        project = projects.first()
        self.stdout.write(self.style.SUCCESS(f'✓ Project created: {project.name}'))
        self.stdout.write(f'  Working directory: {project.working_directory}')
        return project

    def _display_summary(
        self, user, account, project, folders_created=0, docs_created=0
    ):
        """Display a comprehensive summary of everything created."""
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('✓ INITIALIZATION COMPLETE!'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        # User details
        self.stdout.write(self.style.HTTP_INFO('User Details:'))
        self.stdout.write(f'  Username: {user.username}')
        self.stdout.write(f'  Email: {user.email}')
        self.stdout.write('')

        # Organization details
        self.stdout.write(self.style.HTTP_INFO('Organization Details:'))
        self.stdout.write(f'  Name: {account.name}')
        self.stdout.write(f'  Slug: {account.slug}')
        self.stdout.write(f'  Subscription: {account.get_subscription_plan_display()}')
        self.stdout.write(f'  Max Users: {account.max_users}')
        self.stdout.write(f'  Owner: {user.username}')
        self.stdout.write('')

        # Project details
        if project:
            self.stdout.write(self.style.HTTP_INFO('Project Details:'))
            self.stdout.write(f'  Name: {project.name}')
            self.stdout.write(f'  Working Directory: {project.working_directory}')
            if project.worktree_directory:
                self.stdout.write(f'  Worktree Directory: {project.worktree_directory}')

            # Check if directory exists
            working_dir_path = Path(project.working_directory)
            if working_dir_path.exists():
                self.stdout.write(f'  Directory Status: {self.style.SUCCESS("Exists")}')
            else:
                self.stdout.write(
                    f'  Directory Status: {self.style.WARNING("Not created yet - will be created on first use")}'
                )
            self.stdout.write('')

        # Demo documents details
        if docs_created or folders_created:
            self.stdout.write(self.style.HTTP_INFO('Demo Documents:'))
            self.stdout.write(f'  Folders Created: {folders_created}')
            self.stdout.write(f'  Documents Created: {docs_created}')
            self.stdout.write('')

        # Admin links
        self.stdout.write(self.style.HTTP_INFO('Admin Links:'))
        self.stdout.write(f'  Organization: /admin/accounts/account/{account.id}/change/')
        if project:
            self.stdout.write(f'  Project: /admin/projects/project/{project.id}/change/')
        self.stdout.write('')

        # Next steps
        self.stdout.write(self.style.HTTP_INFO('Next Steps:'))
        self.stdout.write('  1. Log in to the admin interface with these credentials')
        self.stdout.write('  2. The project working directory will be created automatically when needed')
        self.stdout.write('  3. You can create additional projects as needed')
        self.stdout.write('')

    def _load_demo_docs(self, project, user, demo_docs_path=None):
        """Load demo documents from the demo-docs directory into the project.

        Scans the demo-docs directory recursively, creating Folder instances for
        subdirectories and Markdown/D2Diagram instances for .md and .d2 files.

        Args:
            project: The Project to load documents into
            user: The User who will own the documents
            demo_docs_path: Optional custom path to demo docs directory

        Returns:
            tuple: (folders_created, docs_created) counts
        """
        # Find the demo-docs directory
        if demo_docs_path:
            demo_dir = Path(demo_docs_path)
        else:
            # Default: look for demo-docs inside zoea-core package
            zoea_core_dir = Path(__file__).resolve().parent.parent.parent.parent
            demo_dir = zoea_core_dir / 'demo-docs'

        if not demo_dir.exists():
            self.stdout.write(
                self.style.WARNING(f'Demo docs directory not found: {demo_dir}')
            )
            return 0, 0

        folders_created = 0
        docs_created = 0
        folder_map = {}  # Map path to Folder instance

        # Walk the directory tree
        for item in sorted(demo_dir.rglob('*')):
            rel_path = item.relative_to(demo_dir)

            if item.is_dir():
                # Create folder
                parent_folder = None
                if rel_path.parent != Path('.'):
                    parent_folder = folder_map.get(rel_path.parent)

                folder = Folder.objects.create(
                    project=project,
                    organization=project.organization,
                    name=item.name,
                    parent=parent_folder,
                    created_by=user,
                )
                folder_map[rel_path] = folder
                folders_created += 1
                self.stdout.write(f'  Created folder: {rel_path}')

            elif item.is_file():
                # Determine parent folder
                parent_folder = None
                if rel_path.parent != Path('.'):
                    parent_folder = folder_map.get(rel_path.parent)

                # Read file content
                try:
                    content = item.read_text(encoding='utf-8')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  Skipped {rel_path}: {e}')
                    )
                    continue

                # Create appropriate document type
                doc_name = item.stem  # Filename without extension

                # Base kwargs for document creation
                doc_kwargs = {
                    'name': doc_name,
                    'content': content,
                    'created_by': user,
                    'folder': parent_folder,
                    'project': project,
                    'organization': project.organization,
                }

                if item.suffix.lower() == '.md':
                    Markdown.objects.create(**doc_kwargs)
                    docs_created += 1
                    self.stdout.write(f'  Created Markdown: {rel_path}')

                elif item.suffix.lower() == '.d2':
                    D2Diagram.objects.create(**doc_kwargs)
                    docs_created += 1
                    self.stdout.write(f'  Created D2 Diagram: {rel_path}')

        return folders_created, docs_created
