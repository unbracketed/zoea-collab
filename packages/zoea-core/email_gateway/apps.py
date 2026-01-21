from django.apps import AppConfig


class EmailGatewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_gateway'
    verbose_name = 'Email Gateway'

    def ready(self):
        from . import signals  # noqa: F401
