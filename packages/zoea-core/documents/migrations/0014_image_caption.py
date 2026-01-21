from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0013_add_attachments_collection"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImageCaption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(help_text="LLM provider used for the caption (openai, gemini, etc.)", max_length=50)),
                ("model", models.CharField(help_text="Model identifier used for the caption", max_length=100)),
                ("caption", models.TextField(help_text="Generated caption text")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "image",
                    models.ForeignKey(
                        help_text="Image document this caption describes",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="captions",
                        to="documents.image",
                    ),
                ),
            ],
            options={
                "verbose_name": "Image Caption",
                "verbose_name_plural": "Image Captions",
                "unique_together": {("image", "provider", "model")},
            },
        ),
        migrations.AddIndex(
            model_name="imagecaption",
            index=models.Index(fields=["image", "provider", "model"], name="doc_image_provider_model_idx"),
        ),
    ]
