from django.apps import AppConfig


class AlmacenamientoConfig(AppConfig):
    name = "almacenamiento"
    verbose_name = "Cargas técnicas de Dani"

    def ready(self):
        from . import schema  # noqa: F401 — esquema JWT de la vista propia.
