from django.apps import AppConfig


class ChoresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chores"

    def ready(self):
        from . import realtime  # noqa: F401
