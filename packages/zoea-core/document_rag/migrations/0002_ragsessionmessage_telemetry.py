from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("document_rag", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ragsessionmessage",
            name="telemetry",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Lightweight run telemetry (tokens, timing, tool usage)",
            ),
        ),
    ]

