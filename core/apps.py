from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        """Charge les signaux de nettoyage des fichiers uploadés."""
        from . import signals  # noqa: F401
