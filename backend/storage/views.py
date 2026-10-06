from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

from common.pagination import EnvelopePagination
from common.responses import fail, ok

from .models import FileMetadata, Folder
from .serializers import FileMetadataSerializer, FolderSerializer

User = get_user_model()


def _build_path(folder):
    if folder.padre:
        return f"{folder.padre.ruta_completa}/{folder.nombre}"
    return f"/{folder.nombre}"


def _propagate_path(folder):
    descendants = []
    stack = [folder]
    while stack:
        current = stack.pop()
        for child in current.subcarpetas.all():
            child.ruta_completa = f"{current.ruta_completa}/{child.nombre}"
            descendants.append(child)
            stack.append(child)
    if descendants:
        Folder.objects.bulk_update(descendants, ["ruta_completa"])


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    pagination_class = EnvelopePagination

    def get_queryset(self):
        return Folder.objects.filter(owner=self.request.user)

    def _filter_by_padre(self, queryset):
        padre = self.request.query_params.get("padre")
        if padre == "null":
            return queryset.filter(padre__isnull=True)
        if padre:
            return queryset.filter(padre_id=padre)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self._filter_by_padre(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ok(serializer.data)

    def _check_duplicate(self, nombre, padre_id, exclude=None):
        qs = Folder.objects.filter(owner=self.request.user, padre_id=padre_id, nombre=nombre)
        if exclude:
            qs = qs.exclude(pk=exclude.pk)
        return qs.exists()

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        nombre = data.get("nombre", "").strip()
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})
        if self._check_duplicate(nombre, None):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return fail("VALIDATION_ERROR", serializer.errors)
        folder = serializer.save(owner=request.user)
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["ruta_completa"])
        return ok(serializer.data, status=201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        folder = self.get_object()
        nombre = request.data.get("nombre", folder.nombre).strip()
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})
        if self._check_duplicate(nombre, folder.padre_id, exclude=folder):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)
        serializer = self.get_serializer(folder, data=request.data, partial=partial)
        if not serializer.is_valid():
            return fail("VALIDATION_ERROR", serializer.errors)
        folder = serializer.save()
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["ruta_completa"])
        _propagate_path(folder)
        return ok(serializer.data)

    def destroy(self, request, *args, **kwargs):
        folder = self.get_object()
        # Al borrar la carpeta, SET_NULL deja sus archivos sin carpeta y CASCADE borra subcarpetas.
        folder.delete()
        return ok(None, status=204)

    @action(detail=True, methods=["get"])
    def contenido(self, request, pk=None):
        folder = self.get_object()
        subcarpetas = folder.subcarpetas.all()
        archivos = folder.archivos.all()
        return ok({
            "subcarpetas": FolderSerializer(subcarpetas, many=True, context={"request": request}).data,
            "archivos": FileMetadataSerializer(archivos, many=True, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        folder = self.get_object()
        padre_id = request.data.get("padre_id")

        if padre_id is None or padre_id == "null":
            nuevo_padre = None
        else:
            try:
                nuevo_padre = Folder.objects.get(pk=padre_id, owner=request.user)
            except (Folder.DoesNotExist, DjangoValidationError):
                return fail("VALIDATION_ERROR", {"padre_id": ["La carpeta indicada no existe."]})

        if nuevo_padre == folder:
            return fail("VALIDATION_ERROR", {"padre_id": ["No se puede mover una carpeta dentro de sí misma."]})

        ancestro = nuevo_padre
        while ancestro:
            if ancestro == folder:
                return fail("VALIDATION_ERROR", {"padre_id": ["No se puede mover una carpeta a una de sus subcarpetas."]})
            ancestro = ancestro.padre

        if Folder.objects.filter(owner=request.user, padre=nuevo_padre, nombre=folder.nombre).exclude(pk=folder.pk).exists():
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)

        folder.padre = nuevo_padre
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["padre", "ruta_completa"])
        _propagate_path(folder)
        return ok(FolderSerializer(folder, context={"request": request}).data)


class FileMetadataViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = FileMetadataSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "patch", "post"]

    TIPOS_CONOCIDOS = {"pdf", "zip", "png", "js", "xlsx", "mp4", "docx"}

    def get_queryset(self):
        return FileMetadata.objects.filter(owner=self.request.user, en_papelera=False)

    def _aplicar_filtros(self, queryset):
        carpeta = self.request.query_params.get("carpeta")
        if carpeta == "null":
            queryset = queryset.filter(carpeta__isnull=True)
        elif carpeta:
            queryset = queryset.filter(carpeta_id=carpeta)

        busqueda = self.request.query_params.get("busqueda")
        if busqueda:
            queryset = queryset.filter(nombre_original__icontains=busqueda)

        tipo = self.request.query_params.get("tipo")
        if tipo in self.TIPOS_CONOCIDOS:
            queryset = queryset.filter(nombre_original__iendswith=f".{tipo}")
        elif tipo == "otro":
            for t in self.TIPOS_CONOCIDOS:
                queryset = queryset.exclude(nombre_original__iendswith=f".{t}")

        return queryset.order_by("-actualizado_en")

    def list(self, request, *args, **kwargs):
        queryset = self._aplicar_filtros(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return ok(serializer.data)

    def update(self, request, *args, **kwargs):
        archivo = self.get_object()
        nombre = request.data.get("nombre", "").strip() if isinstance(request.data.get("nombre"), str) else ""
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre del archivo es obligatorio."]})

        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        data["nombre_original"] = nombre
        serializer = self.get_serializer(archivo, data=data, partial=kwargs.get("partial", False))
        if not serializer.is_valid():
            return fail("VALIDATION_ERROR", serializer.errors)
        serializer.save()
        return ok(serializer.data)

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        archivo = get_object_or_404(self.get_queryset(), pk=pk)
        carpeta_id = request.data.get("carpeta_id")

        if carpeta_id is None or carpeta_id == "null":
            carpeta = None
        else:
            try:
                carpeta = Folder.objects.get(pk=carpeta_id, owner=request.user)
            except (Folder.DoesNotExist, DjangoValidationError):
                return fail("VALIDATION_ERROR", {"carpeta_id": ["La carpeta indicada no existe."]})

        archivo.carpeta = carpeta
        archivo.save(update_fields=["carpeta", "actualizado_en"])
        return ok({
            "id": str(archivo.pk),
            "nombre": archivo.nombre_original,
            "carpeta_id": str(carpeta.pk) if carpeta else None,
            "fecha_modificacion": archivo.actualizado_en,
        })
