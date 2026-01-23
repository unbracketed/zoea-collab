# Generated manually for initial Channels models.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        ("projects", "0001_initial"),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Channel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adapter_type", models.CharField(help_text="Adapter/platform type (slack, discord, email, zoea_chat)", max_length=50)),
                ("external_id", models.CharField(help_text="Platform-specific channel identifier", max_length=255)),
                ("display_name", models.CharField(blank=True, help_text="Human-readable channel name", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        help_text="Organization that owns this channel",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channels",
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional project scope for this channel",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channels",
                        to="projects.project",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional workspace scope for this channel",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channels",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "Channel",
                "verbose_name_plural": "Channels",
                "ordering": ["adapter_type", "display_name", "external_id"],
                "unique_together": {("organization", "adapter_type", "external_id")},
                "indexes": [
                    models.Index(fields=["organization", "adapter_type"], name="channels_ch_organiz_6d3b9f_idx"),
                    models.Index(fields=["organization", "external_id"], name="channels_ch_organiz_b2a5c2_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ChannelMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(blank=True, help_text="Platform-specific message identifier", max_length=255)),
                ("sender_id", models.CharField(blank=True, help_text="Platform-specific sender identifier", max_length=255)),
                ("sender_name", models.CharField(blank=True, help_text="Sender display name", max_length=255)),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System")],
                        default="user",
                        help_text="Message role",
                        max_length=20,
                    ),
                ),
                ("content", models.TextField(help_text="Normalized message content")),
                ("raw_content", models.TextField(blank=True, help_text="Raw platform content")),
                ("attachments", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        help_text="Organization that owns this message",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_messages",
                        to="organizations.organization",
                    ),
                ),
                (
                    "channel",
                    models.ForeignKey(
                        help_text="Channel this message belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="channels.channel",
                    ),
                ),
            ],
            options={
                "verbose_name": "Channel Message",
                "verbose_name_plural": "Channel Messages",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["channel", "created_at"], name="channels_ch_channel_3335c0_idx"),
                    models.Index(fields=["sender_id", "created_at"], name="channels_ch_sender__c12b51_idx"),
                ],
            },
        ),
    ]
