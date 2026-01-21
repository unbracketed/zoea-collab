"""
Management command to create an organization for a user.

This command creates a new Account (Organization) and associates the specified
user as the owner. Useful for setting up new users or migrating existing users
to the multi-tenant architecture.

Usage:
    python manage.py setup_user_organization --username brian --org-name "Citrus Grove"
    python manage.py setup_user_organization --email brian@citrusgrove.tech --org-name "My Company"
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from organizations.models import OrganizationUser, OrganizationOwner

from accounts.models import Account

User = get_user_model()


class Command(BaseCommand):
    help = 'Create an organization for a user and make them the owner'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the user',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email of the user',
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

    def handle(self, *args, **options):
        # Get user by username or email
        username = options.get('username')
        email = options.get('email')

        if not username and not email:
            raise CommandError('Either --username or --email must be provided')

        try:
            if username:
                user = User.objects.get(username=username)
            else:
                user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'User not found')

        # Check if user already has an organization
        existing_orgs = OrganizationUser.objects.filter(user=user)
        if existing_orgs.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'User {user.username} already belongs to {existing_orgs.count()} organization(s):'
                )
            )
            for org_user in existing_orgs:
                self.stdout.write(f'  - {org_user.organization.name}')
            confirm = input('Do you want to create another organization? [y/N] ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Cancelled'))
                return

        # Get organization name
        org_name = options.get('org_name')
        if not org_name:
            # Default to user's name or email
            if user.get_full_name():
                org_name = f"{user.get_full_name()}'s Organization"
            else:
                org_name = f"{user.username}'s Organization"

        # Create the organization
        try:
            account = Account.objects.create(
                name=org_name,
                subscription_plan=options['subscription'],
                max_users=options['max_users'],
                billing_email=user.email,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created organization: {account.name}')
            )
        except Exception as e:
            raise CommandError(f'Error creating organization: {str(e)}')

        # Create OrganizationUser relationship
        try:
            org_user = OrganizationUser.objects.create(
                organization=account,
                user=user,
                is_admin=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Added {user.username} as admin member')
            )
        except Exception as e:
            # Rollback organization creation
            account.delete()
            raise CommandError(f'Error creating organization user: {str(e)}')

        # Make user the owner
        try:
            owner = OrganizationOwner.objects.create(
                organization=account,
                organization_user=org_user,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Made {user.username} the organization owner')
            )
        except Exception as e:
            # Rollback
            org_user.delete()
            account.delete()
            raise CommandError(f'Error creating organization owner: {str(e)}')

        # Display summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Setup complete!'))
        self.stdout.write('')
        self.stdout.write('Organization Details:')
        self.stdout.write(f'  Name: {account.name}')
        self.stdout.write(f'  Slug: {account.slug}')
        self.stdout.write(f'  Subscription: {account.get_subscription_plan_display()}')
        self.stdout.write(f'  Max Users: {account.max_users}')
        self.stdout.write(f'  Owner: {user.username} ({user.email})')
        self.stdout.write('')
        self.stdout.write(
            f'You can manage this organization at: /admin/accounts/account/{account.id}/change/'
        )
