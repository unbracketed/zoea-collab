"""
Management command to set up the Summarize Documents workflow trigger.

Creates an EventTrigger for the documents_selected event type that uses
the summarize-document-collection skill.

Usage:
    python manage.py setup_summarize_workflow [--project-id=N]
"""

from django.core.management.base import BaseCommand

from accounts.models import Account
from events.models import EventTrigger, EventType
from projects.models import Project


class Command(BaseCommand):
    help = "Set up the Summarize Documents workflow trigger"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            help="Project ID to scope the trigger to (optional, org-wide if not specified)",
        )
        parser.add_argument(
            "--org-id",
            type=int,
            help="Organization ID (defaults to first organization)",
        )

    def handle(self, *args, **options):
        # Get organization
        org_id = options.get("org_id")
        if org_id:
            try:
                organization = Account.objects.get(id=org_id)
            except Account.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Organization {org_id} not found"))
                return
        else:
            organization = Account.objects.first()
            if not organization:
                self.stderr.write(
                    self.style.ERROR("No organizations found. Create one first.")
                )
                return

        self.stdout.write(f"Using organization: {organization.name}")

        # Get project if specified
        project = None
        project_id = options.get("project_id")
        if project_id:
            try:
                project = Project.objects.get(id=project_id, organization=organization)
                self.stdout.write(f"Scoping to project: {project.name}")
            except Project.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"Project {project_id} not found in organization {organization.name}"
                    )
                )
                return

        # Check if trigger already exists
        existing = EventTrigger.objects.filter(
            organization=organization,
            event_type=EventType.DOCUMENTS_SELECTED,
            name="Summarize Documents",
        )
        if project:
            existing = existing.filter(project=project)
        else:
            existing = existing.filter(project__isnull=True)

        if existing.exists():
            trigger = existing.first()
            self.stdout.write(
                self.style.WARNING(
                    f"Trigger already exists (ID: {trigger.id}). Updating..."
                )
            )
            trigger.skills = ["summarize-document-collection"]
            trigger.description = "Summarize selected documents and create an executive overview"
            trigger.is_enabled = True
            trigger.agent_config = {
                "max_steps": 20,
                "instructions": "Read each selected document and create comprehensive summaries.",
            }
            trigger.save()
        else:
            trigger = EventTrigger.objects.create(
                organization=organization,
                project=project,
                name="Summarize Documents",
                description="Summarize selected documents and create an executive overview",
                event_type=EventType.DOCUMENTS_SELECTED,
                skills=["summarize-document-collection"],
                is_enabled=True,
                run_async=True,
                filters={},
                agent_config={
                    "max_steps": 20,
                    "instructions": "Read each selected document and create comprehensive summaries.",
                },
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created EventTrigger (ID: {trigger.id})")
            )

        # Print summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Workflow setup complete!"))
        self.stdout.write(f"  Trigger ID: {trigger.id}")
        self.stdout.write(f"  Name: {trigger.name}")
        self.stdout.write(f"  Event Type: {trigger.event_type}")
        self.stdout.write(f"  Skills: {trigger.skills}")
        self.stdout.write(f"  Scope: {project.name if project else 'Organization-wide'}")
        self.stdout.write("")
        self.stdout.write(
            "Select documents in the Files view and use the Workflows dropdown to run this workflow."
        )
