# Generated manually for EmailAttachment model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0006_alter_organization_slug'),
        ('email_gateway', '0002_alter_emailmessage_organization'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(help_text='Uploaded attachment file', upload_to='email_attachments/%Y/%m/%d/')),
                ('filename', models.CharField(help_text='Original filename', max_length=1024)),
                ('content_type', models.CharField(blank=True, help_text='MIME type reported by Mailgun', max_length=255)),
                ('size', models.BigIntegerField(default=0, help_text='Attachment size in bytes')),
                ('content_id', models.CharField(blank=True, help_text='Content-ID from email headers (for inline attachments)', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('email_message', models.ForeignKey(help_text='Parent email message', on_delete=django.db.models.deletion.CASCADE, related_name='stored_attachments', to='email_gateway.emailmessage')),
                ('organization', models.ForeignKey(blank=True, help_text='Organization this attachment belongs to (set during processing)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='email_attachments', to='organizations.organization')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailattachment',
            index=models.Index(fields=['organization'], name='email_gatew_organiz_0a9fa8_idx'),
        ),
        migrations.AddIndex(
            model_name='emailattachment',
            index=models.Index(fields=['email_message'], name='email_gatew_email_me_cb2982_idx'),
        ),
    ]
