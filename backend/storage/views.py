from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action

from auth_workspaces.models import Usuario
from common.ambito import resolver_organizacion
from common.errores import ContratoAPIMixin
from common.pagination import EnvelopePagination
from common.responses import fail, ok

from .models import Archivo, Carpeta
from .serializers import ArchivoSerializer, CarpetaSerializer


def _build_path(folder):
    if folder.padre:
        return f"{folder.padre.ruta_completa}/{folder.nombre}"
    return f"/{folder.nombre}"


def _propagate_path(folder):
    descendants = []
    stack = [folder]
    while stack:
        current = stack.pop()
        for child in current.subcarpetas.filter(en_papelera=False):
            child.ruta_completa = f"{current.ruta_completa}/{child.nombre}"
            descendants.append(child)
            stack.append(child)
    if descendants:
        Carpeta.objects.bulk_update(descendants, ["ruta_completa"])


def _organizacion_id(request):
    org_id = request.query_params.get("organizacion_id")
    if org_id:
        return org_id
    if hasattr(request, "data") and isinstance(request.data, dict):
        return request.data.get("organizacion_id")
    return None


def _normalizar_nombre(nombre):
    if isinstance(nombre, str):
        return nombre.strip()
    return nombre


class CarpetaViewSet(ContratoAPIMixin, viewsets.ModelViewSet):
    serializer_class = CarpetaSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "post", "patch", "delete"]

    def _ambito(self, escritura=False):
        return resolver_organizacion(self.request.user, _organizacion_id(self.request), escritura=escritura)

    def get_queryset(self):
        ambito = self._ambito()
        qs = Carpeta.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False)
        if self.action == "list":
            padre = self.request.query_params.get("carpeta_padre_id")
            if padre in (None, "null", ""):
                qs = qs.filter(padre__isnull=True)
            else:
                qs = qs.filter(padre_id=padre)
            buscar = self.request.query_params.get("buscar")
            if buscar:
                qs = qs.filter(nombre__icontains=buscar)
        return qs.order_by("nombre")

    def _carpeta_existe(self, carpeta_padre_id, organizacion_id):
        if not carpeta_padre_id:
            return True
        return Carpeta.objects.filter(
            pk=carpeta_padre_id, organizacion_id=organizacion_id, en_papelera=False
        ).exists()

    def _nombre_unico_carpeta(self, nombre, carpeta_padre_id, organizacion_id, exclude=None):
        nombre_cf = nombre.casefold()
        qs = Carpeta.objects.filter(
            organizacion_id=organizacion_id, padre_id=carpeta_padre_id, en_papelera=False
        )
        if exclude:
            qs = qs.exclude(pk=exclude.pk)
        return not any(c.nombre.casefold() == nombre_cf for c in qs)

    def create(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        nombre = _normalizar_nombre(data.get("nombre", ""))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})

        carpeta_padre_id = data.get("carpeta_padre_id")
        if carpeta_padre_id in (None, "null", ""):
            carpeta_padre_id = None
        if carpeta_padre_id and not self._carpeta_existe(carpeta_padre_id, ambito.organizacion_id):
            return fail("VALIDATION_ERROR", {"carpeta_padre_id": ["La carpeta padre no existe."]})

        if not self._nombre_unico_carpeta(nombre, carpeta_padre_id, ambito.organizacion_id):
            return fail(
                "VALIDATION_ERROR",
                {"nombre": ["Ya existe una carpeta con ese nombre."]},
                status=409,
            )

        folder = Carpeta.objects.create(
            organizacion_id=ambito.organizacion_id,
            padre_id=carpeta_padre_id,
            propietario=request.user,
            nombre=nombre,
            ruta_completa="/",
        )
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["ruta_completa"])
        return ok(CarpetaSerializer(folder, context={"request": request}).data, status=201)

    def update(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        partial = kwargs.pop("partial", False)
        folder = self.get_object()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        nombre = _normalizar_nombre(data.get("nombre", folder.nombre))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})

        if not self._nombre_unico_carpeta(
            nombre, folder.padre_id, ambito.organizacion_id, exclude=folder
        ):
            return fail(
                "VALIDATION_ERROR",
                {"nombre": ["Ya existe una carpeta con ese nombre."]},
                status=409,
            )

        serializer = self.get_serializer(folder, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        folder = serializer.save()
        folder.nombre = nombre
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["nombre", "ruta_completa"])
        _propagate_path(folder)
        return ok(serializer.data)

    def destroy(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        folder = self.get_object()
        ahora = timezone.now()
        carpetas_a_papelera = []
        stack = [folder]
        while stack:
            actual = stack.pop()
            carpetas_a_papelera.append(actual)
            stack.extend(actual.subcarpetas.filter(en_papelera=False))

        for c in carpetas_a_papelera:
            c.en_papelera = True
            c.fecha_papelera = ahora
        Carpeta.objects.bulk_update(carpetas_a_papelera, ["en_papelera", "fecha_papelera"])

        ids_carpetas = [c.pk for c in carpetas_a_papelera]
        Archivo.objects.filter(
            carpeta_id__in=ids_carpetas, organizacion_id=ambito.organizacion_id, en_papelera=False
        ).update(en_papelera=True, fecha_papelera=ahora)

        return ok({"mensaje": "Carpeta y su contenido movidos a la papelera de reciclaje."})

    @action(detail=True, methods=["get"])
    def contenido(self, request, pk=None):
        self._ambito(escritura=False)
        folder = self.get_object()
        subcarpetas = folder.subcarpetas.filter(en_papelera=False)
        archivos = folder.archivos.filter(en_papelera=False)
        return ok({
            "subcarpetas": CarpetaSerializer(subcarpetas, many=True, context={"request": request}).data,
            "archivos": ArchivoSerializer(archivos, many=True, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        ambito = self._ambito(escritura=True)
        folder = self.get_object()
        padre_id = request.data.get("padre_id")
        if padre_id in (None, "null", ""):
            nuevo_padre = None
        else:
            try:
                nuevo_padre = Carpeta.objects.get(
                    pk=padre_id, organizacion_id=ambito.organizacion_id, en_papelera=False
                )
            except (Carpeta.DoesNotExist, DjangoValidationError):
                return fail("VALIDATION_ERROR", {"padre_id": ["La carpeta indicada no existe."]})

        if nuevo_padre == folder:
            return fail("VALIDATION_ERROR", {"padre_id": ["No se puede mover una carpeta dentro de sí misma."]})

        ancestro = nuevo_padre
        while ancestro:
            if ancestro == folder:
                return fail(
                    "VALIDATION_ERROR",
                    {"padre_id": ["No se puede mover una carpeta a una de sus subcarpetas."]},
                )
            ancestro = ancestro.padre

        if not self._nombre_unico_carpeta(
            folder.nombre, nuevo_padre.pk if nuevo_padre else None, ambito.organizacion_id, exclude=folder
        ):
            return fail(
                "VALIDATION_ERROR",
                {"nombre": ["Ya existe una carpeta con ese nombre."]},
                status=409,
            )

        folder.padre = nuevo_padre
        folder.ruta_completa = _build_path(folder)
        folder.save(update_fields=["padre", "ruta_completa"])
        _propagate_path(folder)
        return ok(CarpetaSerializer(folder, context={"request": request}).data)


class ArchivoViewSet(
    ContratoAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ArchivoSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "patch", "post"]

    TIPOS_CONOCIDOS = {"pdf", "zip", "png", "js", "xlsx", "mp4", "docx"}

    def _ambito(self, escritura=False):
        return resolver_organizacion(self.request.user, _organizacion_id(self.request), escritura=escritura)

    def get_queryset(self):
        ambito = self._ambito()
        qs = Archivo.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False)

        if self.action == "list":
            carpeta = self.request.query_params.get("carpeta_id")
            if carpeta in (None, "null", ""):
                qs = qs.filter(carpeta__isnull=True)
            else:
                qs = qs.filter(carpeta_id=carpeta)

            buscar = self.request.query_params.get("buscar")
            if buscar:
                qs = qs.filter(nombre_original__icontains=buscar)

            tipo = self.request.query_params.get("tipo")
            if tipo in self.TIPOS_CONOCIDOS:
                qs = qs.filter(nombre_original__iendswith=f".{tipo}")
            elif tipo == "otro":
                for t in self.TIPOS_CONOCIDOS:
                    qs = qs.exclude(nombre_original__iendswith=f".{t}")

        return qs.order_by("-actualizado_en")

    def _nombre_unico_archivo(self, nombre, carpeta_id, organizacion_id, exclude=None):
        nombre_cf = nombre.casefold()
        qs = Archivo.objects.filter(
            organizacion_id=organizacion_id, carpeta_id=carpeta_id, en_papelera=False
        )
        if exclude:
            qs = qs.exclude(pk=exclude.pk)
        return not any(a.nombre_original.casefold() == nombre_cf for a in qs)

    def update(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        archivo = self.get_object()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        nombre = _normalizar_nombre(data.get("nombre"))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre del archivo es obligatorio."]})
        data["nombre_original"] = nombre

        if not self._nombre_unico_archivo(
            nombre, archivo.carpeta_id, ambito.organizacion_id, exclude=archivo
        ):
            return fail(
                "VALIDATION_ERROR",
                {"nombre": ["Ya existe un archivo con ese nombre."]},
                status=409,
            )

        serializer = self.get_serializer(archivo, data=data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ok(serializer.data)

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        ambito = self._ambito(escritura=True)
        archivo = get_object_or_404(self.get_queryset(), pk=pk)
        carpeta_id = request.data.get("carpeta_id")
        if carpeta_id in (None, "null", ""):
            carpeta = None
        else:
            try:
                carpeta = Carpeta.objects.get(
                    pk=carpeta_id, organizacion_id=ambito.organizacion_id, en_papelera=False
                )
            except (Carpeta.DoesNotExist, DjangoValidationError):
                return fail("VALIDATION_ERROR", {"carpeta_id": ["La carpeta indicada no existe."]})

        if not self._nombre_unico_archivo(
            archivo.nombre_original, carpeta_id, ambito.organizacion_id, exclude=archivo
        ):
            return fail(
                "VALIDATION_ERROR",
                {"nombre": ["Ya existe un archivo con ese nombre."]},
                status=409,
            )

        archivo.carpeta = carpeta
        archivo.save(update_fields=["carpeta", "actualizado_en"])
        return ok(ArchivoSerializer(archivo, context={"request": request}).data)
