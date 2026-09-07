from django.apps import AppConfig


class AnnouncementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "announcements"

    def ready(self):
        # Registers the deployment checks (see checks.py).
        from . import checks  # noqa: F401
