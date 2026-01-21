from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("context_clipboards", "0002_alter_clipboarditem_object_id_and_more"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="clipboard",
            name="context_cli_clipboa_6a9d2c_idx",
        ),
        migrations.RemoveIndex(
            model_name="clipboarditem",
            name="context_cli_is_impl_980820_idx",
        ),
        migrations.RemoveConstraint(
            model_name="clipboard",
            name="unique_active_clipboard_per_user_and_type",
        ),
        migrations.RemoveField(
            model_name="clipboard",
            name="clipboard_type",
        ),
        migrations.RemoveField(
            model_name="clipboard",
            name="mirror_to_workspace",
        ),
        migrations.RemoveField(
            model_name="clipboarditem",
            name="is_implicit",
        ),
        migrations.RemoveField(
            model_name="clipboarditem",
            name="mirrored_from",
        ),
        migrations.AddConstraint(
            model_name="clipboard",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("workspace", "owner"),
                name="unique_active_clipboard_per_user",
            ),
        ),
        migrations.DeleteModel(
            name="ContextClipboard",
        ),
        migrations.DeleteModel(
            name="WorkspaceClipboard",
        ),
    ]
