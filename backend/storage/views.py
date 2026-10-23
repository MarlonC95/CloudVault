from uuid import UUID

from django.db import connections, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from almacenamiento.configuracion_s3 import ConfiguracionS3, ConfiguracionS3Invalida
from almacenamiento.s3 import ClienteS3, ErrorS3
from common.ambito import resolver_organizacion
from common.errores import ContratoAPIMixin
from common.formatting import bytes_legibles
from common.pagination import EnvelopePagination
from common.responses import fail, ok
from subscriptions.cuotas import SinSuscripcionVigente

from .models import Archivo, Carpeta
from .serializers import ArchivoSerializer, CarpetaSerializer, PapeleraSerializer
from .servicios import leer_cuota_desplegada


def _organizacion_id(request):
    pedido = request.query_params.get("organizacion_id")
    if pedido or request.method == "GET":
        return pedido
    return request.data.get("organizacion_id")


def _nombre(valor):
    return valor.strip() if isinstance(valor, str) else ""


def _uuid(valor):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


class CarpetaViewSet(ContratoAPIMixin, viewsets.ModelViewSet):
    serializer_class = CarpetaSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "post", "patch", "delete"]

    def retrieve(self, request, *args, **kwargs):
        return ok(self.get_serializer(self.get_object()).data)

    def _ambito(self, escritura=False):
        return resolver_organizacion(self.request.user, _organizacion_id(self.request), escritura=escritura)

    def get_queryset(self):
        ambito = self._ambito()
        qs = Carpeta.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False)
        if self.action == "list":
            padre = self.request.query_params.get("padre")
            if padre is None:
                padre = self.request.query_params.get("carpeta_padre_id")
            if padre in ("null", ""):
                qs = qs.filter(padre__isnull=True)
            elif padre is not None:
                identificador = _uuid(padre)
                qs = qs.filter(padre_id=identificador) if identificador else qs.none()
            buscar = self.request.query_params.get("busqueda") or self.request.query_params.get("buscar")
            if buscar:
                qs = qs.filter(nombre__icontains=buscar)
        return qs.order_by("nombre")

    def _padre(self, valor, organizacion_id):
        if valor in (None, "null", ""):
            return None
        identificador = _uuid(valor)
        if identificador is None:
            return False
        return Carpeta.objects.filter(pk=identificador, organizacion_id=organizacion_id, en_papelera=False).first() or False

    def _nombre_unico(self, nombre, padre_id, organizacion_id, exclude=None):
        qs = Carpeta.objects.filter(organizacion_id=organizacion_id, padre_id=padre_id, en_papelera=False)
        if exclude:
            qs = qs.exclude(pk=exclude.pk)
        return not qs.filter(nombre__iexact=nombre).exists()

    def create(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        nombre = _nombre(request.data.get("nombre"))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})
        padre = self._padre(request.data.get("padre_id", request.data.get("carpeta_padre_id")), ambito.organizacion_id)
        if padre is False:
            return fail("VALIDATION_ERROR", {"padre_id": ["La carpeta padre no existe."]})
        if not self._nombre_unico(nombre, padre.pk if padre else None, ambito.organizacion_id):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)
        carpeta = Carpeta.objects.create(organizacion_id=ambito.organizacion_id, padre=padre, nombre=nombre)
        return ok(self.get_serializer(carpeta).data, status=201)

    def update(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        carpeta = self.get_object()
        nombre = _nombre(request.data.get("nombre"))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre de la carpeta es obligatorio."]})
        if not self._nombre_unico(nombre, carpeta.padre_id, ambito.organizacion_id, carpeta):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)
        carpeta.nombre = nombre
        carpeta.save(update_fields=["nombre"])
        return ok(self.get_serializer(carpeta).data)

    def destroy(self, request, *args, **kwargs):
        self._ambito(escritura=True)
        carpeta = self.get_object()
        with transaction.atomic():
            # Las referencias de archivos se conservan incluso en descendientes.
            ids = []
            pendientes = [carpeta]
            while pendientes:
                actual = pendientes.pop()
                ids.append(actual.pk)
                pendientes.extend(actual.subcarpetas.all())
            Archivo.objects.filter(carpeta_id__in=ids).update(carpeta=None)
            carpeta.delete()
        return Response(status=204)

    @action(detail=True, methods=["get"])
    def contenido(self, request, pk=None):
        carpeta = self.get_object()
        return ok({
            "subcarpetas": CarpetaSerializer(carpeta.subcarpetas.filter(en_papelera=False), many=True).data,
            "archivos": ArchivoSerializer(carpeta.archivos.filter(en_papelera=False), many=True).data,
        })

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        ambito = self._ambito(escritura=True)
        carpeta = self.get_object()
        padre = self._padre(request.data.get("padre_id"), ambito.organizacion_id)
        if padre is False:
            return fail("VALIDATION_ERROR", {"padre_id": ["La carpeta indicada no existe."]})
        ancestro = padre
        while ancestro:
            if ancestro.pk == carpeta.pk:
                return fail("VALIDATION_ERROR", {"padre_id": ["No se puede mover una carpeta dentro de sí misma."]})
            ancestro = ancestro.padre
        if not self._nombre_unico(carpeta.nombre, padre.pk if padre else None, ambito.organizacion_id, carpeta):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe una carpeta con ese nombre."]}, status=409)
        carpeta.padre = padre
        carpeta.save(update_fields=["padre"])
        return ok(self.get_serializer(carpeta).data)


class ArchivoViewSet(ContratoAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    serializer_class = ArchivoSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "patch", "post", "delete"]
    TIPOS_CONOCIDOS = {"pdf", "zip", "png", "js", "xlsx", "mp4", "docx"}

    def retrieve(self, request, *args, **kwargs):
        return ok(self.get_serializer(self.get_object()).data)

    def _ambito(self, escritura=False):
        return resolver_organizacion(self.request.user, _organizacion_id(self.request), escritura=escritura)

    def get_queryset(self):
        ambito = self._ambito()
        qs = Archivo.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False).select_related("propietario", "carpeta")
        if self.action == "list":
            carpeta = self.request.query_params.get("carpeta", self.request.query_params.get("carpeta_id"))
            if carpeta not in (None, "", "null"):
                identificador = _uuid(carpeta)
                qs = qs.filter(carpeta_id=identificador) if identificador else qs.none()
            elif "carpeta" not in self.request.query_params and carpeta in ("", "null"):
                qs = qs.filter(carpeta__isnull=True)
            buscar = self.request.query_params.get("busqueda") or self.request.query_params.get("buscar")
            if buscar:
                qs = qs.filter(nombre__icontains=buscar)
            tipo = self.request.query_params.get("tipo")
            if tipo in self.TIPOS_CONOCIDOS:
                qs = qs.filter(nombre__iendswith=f".{tipo}")
            elif tipo == "otro":
                for extension in self.TIPOS_CONOCIDOS:
                    qs = qs.exclude(nombre__iendswith=f".{extension}")
        return qs.order_by("-actualizado_en")

    def _nombre_unico(self, nombre, carpeta_id, organizacion_id, exclude=None):
        qs = Archivo.objects.filter(organizacion_id=organizacion_id, carpeta_id=carpeta_id, en_papelera=False)
        if exclude:
            qs = qs.exclude(pk=exclude.pk)
        return not qs.filter(nombre__iexact=nombre).exists()

    def partial_update(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        archivo = self.get_object()
        nombre = _nombre(request.data.get("nombre"))
        if not nombre:
            return fail("VALIDATION_ERROR", {"nombre": ["El nombre del archivo es obligatorio."]})
        if not self._nombre_unico(nombre, archivo.carpeta_id, ambito.organizacion_id, archivo):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe un archivo con ese nombre."]}, status=409)
        archivo.nombre = nombre
        archivo.save(update_fields=["nombre", "actualizado_en"])
        return ok(self.get_serializer(archivo).data)

    def destroy(self, request, *args, **kwargs):
        self._ambito(escritura=True)
        archivo = self.get_object()
        archivo.en_papelera = True
        archivo.fecha_papelera = timezone.now()
        archivo.save(update_fields=["en_papelera", "fecha_papelera", "actualizado_en"])
        return ok({"mensaje": "El archivo se movió a la papelera."})

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        ambito = self._ambito(escritura=True)
        archivo = self.get_object()
        valor = request.data.get("carpeta_id")
        if valor in (None, "", "null"):
            carpeta = None
        else:
            identificador = _uuid(valor)
            carpeta = Carpeta.objects.filter(pk=identificador, organizacion_id=ambito.organizacion_id, en_papelera=False).first() if identificador else None
            if carpeta is None:
                return fail("VALIDATION_ERROR", {"carpeta_id": ["La carpeta indicada no existe."]})
        if not self._nombre_unico(archivo.nombre, carpeta.pk if carpeta else None, ambito.organizacion_id, archivo):
            return fail("VALIDATION_ERROR", {"nombre": ["Ya existe un archivo con ese nombre."]}, status=409)
        archivo.carpeta = carpeta
        archivo.save(update_fields=["carpeta", "actualizado_en"])
        return ok(self.get_serializer(archivo).data)


class PapeleraViewSet(ContratoAPIMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PapeleraSerializer
    pagination_class = EnvelopePagination
    http_method_names = ["get", "post", "delete"]

    def _ambito(self, escritura=False):
        return resolver_organizacion(self.request.user, _organizacion_id(self.request), escritura=escritura)

    def get_queryset(self):
        return Archivo.objects.filter(organizacion_id=self._ambito().organizacion_id, en_papelera=True).order_by("-fecha_papelera")

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        self._ambito(escritura=True)
        archivo = self.get_object()
        if archivo.carpeta_id and (archivo.carpeta.en_papelera or archivo.carpeta.organizacion_id != archivo.organizacion_id):
            archivo.carpeta = None
        archivo.en_papelera = False
        archivo.fecha_papelera = None
        archivo.save(update_fields=["carpeta", "en_papelera", "fecha_papelera", "actualizado_en"])
        return ok({"mensaje": "El archivo se restauró correctamente."})

    def destroy(self, request, *args, **kwargs):
        self._ambito(escritura=True)
        archivo = self.get_object()
        try:
            cliente = ClienteS3(ConfiguracionS3.desde_entorno())
            try:
                cliente.borrar_tecnico(archivo.clave_s3)
            finally:
                cliente.cerrar()
        except (ConfiguracionS3Invalida, ErrorS3, ValueError):
            return fail("SERVICE_UNAVAILABLE", status=503)
        archivo.delete()
        return Response(status=204)


class ResumenUnidadView(ContratoAPIMixin, APIView):
    def get(self, request):
        ambito = resolver_organizacion(request.user, _organizacion_id(request))
        try:
            limite, _, _ = leer_cuota_desplegada(ambito.organizacion_id)
        except SinSuscripcionVigente:
            return fail("SERVICE_UNAVAILABLE", status=503)
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT almacenamiento_usado_bytes FROM organizaciones WHERE id = %s", [ambito.organizacion_id])
            fila = cursor.fetchone()
        if fila is None:
            return fail("NO_ENCONTRADO", status=404)
        usado = fila[0]
        archivos = Archivo.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False)
        categorias = []
        for etiqueta, extensiones, color in (
            ("Documentos", ("pdf", "docx", "xlsx"), "#2563EB"),
            ("Backups", ("zip",), "#7C3AED"),
        ):
            condicion = Q()
            for extension in extensiones:
                condicion |= Q(nombre__iendswith=f".{extension}")
            tamano = archivos.filter(condicion).aggregate(total=Sum("tamano_bytes"))["total"] or 0
            categorias.append({"etiqueta": etiqueta, "tamano_legible": bytes_legibles(tamano), "color": color})
        clasificado = sum(archivos.filter(nombre__iendswith=f".{extension}").aggregate(total=Sum("tamano_bytes"))["total"] or 0 for extension in ("pdf", "docx", "xlsx", "zip"))
        categorias.append({"etiqueta": "Otros", "tamano_legible": bytes_legibles(max(0, (archivos.aggregate(total=Sum("tamano_bytes"))["total"] or 0) - clasificado)), "color": "#0891B2"})
        return ok({
            "usado_bytes": usado, "cuota_bytes": limite,
            "usado_legible": bytes_legibles(usado), "cuota_legible": bytes_legibles(limite),
            "libre_legible": bytes_legibles(max(0, limite - usado)),
            "porcentaje_usado": min(100, round(usado * 100 / limite)) if limite else 0,
            "cantidad_archivos": archivos.count(),
            "cantidad_carpetas": Carpeta.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=False).count(),
            "por_categoria": categorias,
        })
