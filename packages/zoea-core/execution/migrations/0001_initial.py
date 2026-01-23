# Generated manually for initial ExecutionRun model.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        ("projects", "0001_initial"),
        ("workspaces", "0001_initial"),
        ("documents", "0010_alter_collection_options_alter_collection_created_by_and_more"),
        ("events", "0001_initial"),
        ("channels", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExecutionRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "run_id",
                    models.CharField(
                        default=uuid.uuid4,
                        help_text="Unique identifier for this execution run",
                        max_length=36,
                        unique=True,
                    ),
                ),
                (
                    "trigger_type",
                    models.CharField(
                        blank=True,
                        help_text="Normalized trigger type (chat_message, email_received, etc.)",
                        max_length=50,
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        blank=True,
                        help_text="Type of source that triggered this run",
                        max_length=50,
                    ),
                ),
                (
                    "source_id",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="ID of the source object that triggered this run",
                        null=True,
                    ),
                ),
                (
                    "workflow_slug",
                    models.CharField(
                        blank=True,
                        help_text="Workflow slug executed in this run",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "graph_id",
                    models.CharField(
                        blank=True,
                        help_text="LangGraph graph identifier",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        help_text="Current execution status",
                        max_length=20,
                    ),
                ),
                (
                    "input_envelope",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Normalized trigger envelope",
                    ),
                ),
                (
                    "inputs",
                    models.JSONField(
                        default=dict,
                        help_text="Input parameters provided to the run",
                    ),
                ),
                (
                    "outputs",
                    models.JSONField(
                        blank=True,
                        help_text="Output results from execution",
                        null=True,
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        help_text="Error message if execution failed",
                        null=True,
                    ),
                ),
                (
                    "telemetry",
                    models.JSONField(
                        blank=True,
                        help_text="Execution telemetry (token usage, timing, steps)",
                        null=True,
                    ),
                ),
                (
                    "provider_model",
                    models.CharField(
                        blank=True,
                        help_text="AI provider/model used (e.g., 'openai/gpt-4o')",
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "token_usage",
                    models.JSONField(
                        blank=True,
                        help_text="Token usage breakdown",
                        null=True,
                    ),
                ),
                (
                    "task_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Background task ID",
                        max_length=100,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "artifacts",
                    models.ForeignKey(
                        blank=True,
                        help_text="Artifacts produced by this run",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="execution_runs",
                        to="documents.documentcollection",
                    ),
                ),
                (
                    "channel",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional channel context",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="execution_runs",
                        to="channels.channel",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who initiated this run",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="execution_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        help_text="Organization that owns this run",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="execution_runs",
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional project scope",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="execution_runs",
                        to="projects.project",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional workspace scope",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="execution_runs",
                        to="workspaces.workspace",
                    ),
                ),
                (
                    "trigger",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional trigger that initiated this run",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="execution_runs",
                        to="events.eventtrigger",
                    ),
                ),
            ],
            options={
                "verbose_name": "Execution Run",
                "verbose_name_plural": "Execution Runs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["organization", "status"], name="execution_ex_organiz_55ebd6_idx"),
                    models.Index(fields=["organization", "trigger_type"], name="execution_ex_organiz_1cc102_idx"),
                    models.Index(fields=["workflow_slug", "created_at"], name="execution_ex_workfl_0c6d6d_idx"),
                    models.Index(fields=["source_type", "source_id"], name="execution_ex_source_139d33_idx"),
                ],
            },
        ),
    ]
