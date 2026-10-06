from django.db.models import Sum

from .models import FileMetadata


def get_used_bytes(user):
    """Bytes ocupados por los archivos del usuario (la papelera aún cuenta hasta la purga)."""
    return FileMetadata.objects.filter(owner=user).aggregate(total=Sum("tamano_bytes"))["total"] or 0
