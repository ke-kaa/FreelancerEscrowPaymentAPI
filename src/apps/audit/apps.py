from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "platform_audit"  # avoid clash with django-auditlog

    def ready(self):
        # Importing the signals module registers receivers.
        from . import signals  # noqa: F401
