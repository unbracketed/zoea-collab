"""
Management command to test the live music event extraction workflow.

Creates a sample email, event trigger, and runs the extraction skill.

Usage:
    python manage.py test_music_event_extraction --org-slug=<slug> [--project-id=<id>]
"""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Account
from events.dispatcher import dispatch_event
from execution.models import ExecutionRun
from events.models import EventTrigger, EventType
from projects.models import Project

User = get_user_model()

SAMPLE_EMAIL_CONTENT = """
Subject: February Shows at The Fillmore - Don't Miss These!

Hey music lovers,

We've got an incredible lineup coming to The Fillmore this February. Here's what's on tap:

---

**FRIDAY, FEBRUARY 14, 2025**
THE MOUNTAIN GOATS
with special guest Jake Xerxes Fussell

Doors: 7:00 PM | Show: 8:00 PM
Tickets: $35 advance / $40 door
Ages 21+

The legendary John Darnielle brings his literary indie folk to our stage for Valentine's Day. This is going to be a special one.

Buy tickets: https://ticketmaster.com/mountain-goats-fillmore

---

**SATURDAY, FEBRUARY 22, 2025**
JAPANESE BREAKFAST
with opening act Wednesday

Doors: 6:30 PM | Show: 7:30 PM
Tickets: $45 advance / $50 door
All Ages

Michelle Zauner returns to SF in support of her latest album. Don't miss this!

Buy tickets: https://ticketmaster.com/japanese-breakfast-fillmore

---

**WEDNESDAY, FEBRUARY 26, 2025**
KING GIZZARD & THE LIZARD WIZARD
with Leah Senior

Doors: 7:00 PM | Show: 8:00 PM
Tickets: $55 advance / $60 door
Ages 18+

The Aussie psych-rock kings bring their marathon sets to The Fillmore. Prepare for a wild ride!

Buy tickets: https://ticketmaster.com/king-gizzard-fillmore

---

The Fillmore
1805 Geary Blvd
San Francisco, CA 94115

See you at the shows!
- The Fillmore Team
"""


class Command(BaseCommand):
    help = "Test the live music event extraction workflow with a sample email"

    def add_arguments(self, parser):
        parser.add_argument(
            "--org-slug",
            type=str,
            required=True,
            help="Organization slug to use for the test",
        )
        parser.add_argument(
            "--project-id",
            type=int,
            help="Project ID to use (optional, creates trigger at org level if not provided)",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run synchronously instead of queuing to background",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only create trigger and show what would happen, don't dispatch",
        )

    def handle(self, *args, **options):
        org_slug = options["org_slug"]
        project_id = options.get("project_id")
        run_sync = options.get("sync", False)
        dry_run = options.get("dry_run", False)

        # Get organization
        try:
            organization = Account.objects.get(slug=org_slug)
        except Account.DoesNotExist:
            raise CommandError(f"Organization with slug '{org_slug}' not found")

        self.stdout.write(f"Using organization: {organization.name}")

        # Get project if specified
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id, organization=organization)
                self.stdout.write(f"Using project: {project.name}")
            except Project.DoesNotExist:
                raise CommandError(
                    f"Project {project_id} not found in organization '{org_slug}'"
                )

        # Get or create user for the trigger
        user = organization.users.first()
        if not user:
            raise CommandError(f"No users found in organization '{org_slug}'")

        # Create or get the event trigger
        trigger, created = EventTrigger.objects.get_or_create(
            organization=organization,
            project=project,
            name="Live Music Event Extractor",
            event_type=EventType.EMAIL_RECEIVED,
            defaults={
                "skills": ["extract-live-music-events"],
                "is_enabled": True,
                "run_async": not run_sync,
                "filters": {},  # No filters - trigger on all emails
                "agent_config": {
                    "max_steps": 15,
                    "instructions": "Extract all live music events from this email and create artifacts for each.",
                    "use_harness": True,
                    "allowed_external_domains": ["ticketmaster.com", "eventbrite.com"],
                },
                "created_by": user,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created new trigger: {trigger.name} (ID: {trigger.id})")
            )
        else:
            self.stdout.write(f"Using existing trigger: {trigger.name} (ID: {trigger.id})")

        # Show trigger configuration
        self.stdout.write("\nTrigger Configuration:")
        self.stdout.write(f"  Event Type: {trigger.event_type}")
        self.stdout.write(f"  Skills: {trigger.skills}")
        self.stdout.write(f"  Run Async: {trigger.run_async}")
        self.stdout.write(f"  Enabled: {trigger.is_enabled}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n--dry-run specified, not dispatching event")
            )
            self.stdout.write("\nSample email content:")
            self.stdout.write("-" * 60)
            self.stdout.write(SAMPLE_EMAIL_CONTENT[:500] + "...")
            return

        # Build event data simulating an email
        event_data = {
            "subject": "February Shows at The Fillmore - Don't Miss These!",
            "sender": "newsletter@thefillmore.com",
            "body": SAMPLE_EMAIL_CONTENT,
            "received_at": "2025-01-08T10:00:00Z",
            "thread_id": None,
            "attachments": [],
        }

        self.stdout.write("\nDispatching event...")
        self.stdout.write(f"  Event Type: {EventType.EMAIL_RECEIVED}")
        self.stdout.write(f"  Source: email_message (ID: 999)")  # Fake source

        # Dispatch the event
        runs = dispatch_event(
            event_type=EventType.EMAIL_RECEIVED,
            source_type="email_message",
            source_id=999,  # Fake ID for testing
            event_data=event_data,
            organization=organization,
            project=project,
        )

        if not runs:
            self.stdout.write(
                self.style.WARNING("No triggers matched the event")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"\nCreated {len(runs)} trigger run(s)")
        )

        for run in runs:
            self.stdout.write(f"\nTrigger Run: {run.run_id}")
            self.stdout.write(f"  Status: {run.status}")
            self.stdout.write(f"  Trigger: {run.trigger.name}")

            if run_sync:
                # Refresh from DB to get updated status
                run.refresh_from_db()
                self.stdout.write(f"  Final Status: {run.status}")

                if run.outputs:
                    self.stdout.write("\n  Outputs:")
                    self.stdout.write(
                        json.dumps(run.outputs, indent=4, default=str)
                    )

                if run.error:
                    self.stdout.write(
                        self.style.ERROR(f"\n  Error: {run.error}")
                    )

                if run.telemetry:
                    self.stdout.write("\n  Telemetry:")
                    # Show key telemetry without full audit log
                    telemetry_summary = {
                        k: v
                        for k, v in run.telemetry.items()
                        if k != "audit_log"
                    }
                    self.stdout.write(
                        json.dumps(telemetry_summary, indent=4, default=str)
                    )
            else:
                self.stdout.write(
                    "\n  Run is queued for async execution."
                )
                self.stdout.write(
                    "  Check status with: "
                    f"python manage.py shell -c \"from execution.models import ExecutionRun; "
                    f"print(ExecutionRun.objects.get(id={run.id}).status)\""
                )

        # Show how to check results
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("To view all trigger runs:")
        self.stdout.write(
            f"  ExecutionRun.objects.filter(trigger_id={trigger.id})"
        )
