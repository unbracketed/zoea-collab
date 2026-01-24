from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0005_jsoncanvas_mermaiddiagram_and_more"),
        ("organizations", "0006_alter_organization_slug"),
        ("projects", "0002_project_gemini_store_id_project_gemini_store_name_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentPreview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "preview_kind",
                    models.CharField(
                        choices=[
                            ("thumbnail", "Thumbnail"),
                            ("snippet", "Snippet"),
                            ("large", "Large"),
                        ],
                        default="thumbnail",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processing", "Processing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "content_hash",
                    models.CharField(
                        blank=True,
                        help_text="Hash of underlying content used for cache invalidation",
                        max_length=128,
                    ),
                ),
                (
                    "target_hash",
                    models.CharField(
                        blank=True, help_text="Hash this preview was generated against", max_length=128
                    ),
                ),
                (
                    "preview_file",
                    models.ImageField(
                        blank=True,
                        help_text="Generated preview image (WebP/PNG)",
                        null=True,
                        upload_to="previews/%Y/%m/%d/",
                    ),
                ),
                (
                    "preview_html",
                    models.TextField(
                        blank=True, help_text="Sanitized HTML snippet for text-based previews"
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True, default=dict, help_text="Flexible metadata (dominant color, snippet, source info)"
                    ),
                ),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("file_size", models.PositiveIntegerField(blank=True, null=True)),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="previews",
                        to="documents.document",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        help_text="Organization for multi-tenant scoping",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        help_text="Project scope for this preview",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "verbose_name": "Document Preview",
                "verbose_name_plural": "Document Previews",
                "indexes": [
                    models.Index(
                        fields=["organization", "project", "status"],
                        name="docpreview_scope_status",
                    ),
                ],
                "unique_together": {("document", "preview_kind")},
            },
        ),
    ]
