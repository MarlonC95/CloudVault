from collections.abc import Mapping
from types import SimpleNamespace
from uuid import UUID

from django.db import connections
from django.db.models import F, Q, Sum
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.s3 import ClienteS3
from common.ambito import resolver_organizacion
from common.errores import ContratoAPIMixin
from common.formatting import bytes_legibles
from common.pagination import EnvelopePagination
from common.responses import fail, ok
from subscriptions.cuotas import SinSuscripcionVigente

from .models import Archivo, Carpeta
from .papelera import ErrorPapelera, ServicioPapelera, identificador
from .repositorio_papelera import RepositorioPapelera
from .serializers import ArchivoSerializer, CarpetaSerializer, PapeleraSerializer
from .servicios import leer_cuota_desplegada


def _organizacion_id(request):
    pedido = request.query_params.get("organizacion_id")
    if pedido or request.method == "GET":
        return pedido
    return request.data.get("organizacion_id")


def _datos_mutacion_archivo(request, pk):
    archivo_id = identificador(pk)
    if not isinstance(request.data, Mapping):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"non_field_errors": ["El cuerpo debe ser un objeto JSON."]})
    query = request.query_params.get("organizacion_id")
    cuerpo = request.data.get("organizacion_id")
    if query and cuerpo and identificador(query) != identificador(cuerpo):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"organizacion_id": ["El ámbito de la solicitud no coincide."]})
    ambito = resolver_organizacion(request.user, _organizacion_id(request))
    return {"solicitante_id": request.user.pk, "organizacion_id": ambito.organizacion_id,
            "archivo_id": archivo_id}


def _ambito_mutacion(request):
    from rest_framework.exceptions import ValidationError

    if not isinstance(request.data, Mapping) or set(request.data) - {"organizacion_id"}:
        raise ValidationError({"non_field_errors": ["El cuerpo de la solicitud no es válido."]})
    query = request.query_params.get("organizacion_id")
    cuerpo = request.data.get("organizacion_id")
    if query and cuerpo and identificador(query) != identificador(cuerpo):
        raise ValidationError({"organizacion_id": ["El ámbito de la solicitud no coincide."]})
    return resolver_organizacion(request.user, query or cuerpo, escritura=True)


def _nombre(valor):
    return valor.strip() if isinstance(valor, str) else ""


def _uuid(valor):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


def coordinar_carpeta(metodo):
    from functools import wraps
    @wraps(metodo)
    def ejecutar(self, request, *args, **kwargs):
        ambito = self._ambito(escritura=True)
        with RepositorioPapelera().transaccion(ambito.organizacion_id):
            return metodo(self, request, *args, **kwargs)
    return ejecutar


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
        return RepositorioPapelera().nombre_disponible(
            organizacion_id, padre_id, nombre, excluir_carpeta=exclude.pk if exclude else None)

    @coordinar_carpeta
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

    @coordinar_carpeta
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
        ambito = _ambito_mutacion(request)
        from .lotes_papelera import ServicioLotesCarpeta
        ServicioLotesCarpeta().enviar(
            solicitante_id=request.user.pk,
            organizacion_id=ambito.organizacion_id,
            carpeta_id=kwargs.get("pk"),
        )
        return Response(status=204)

    @action(detail=True, methods=["get"])
    def contenido(self, request, pk=None):
        carpeta = self.get_object()
        return ok({
            "subcarpetas": CarpetaSerializer(carpeta.subcarpetas.filter(en_papelera=False), many=True).data,
            "archivos": ArchivoSerializer(carpeta.archivos.filter(en_papelera=False), many=True).data,
        })

    @action(detail=True, methods=["post"])
    @coordinar_carpeta
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
        return RepositorioPapelera().nombre_disponible(
            organizacion_id, carpeta_id, nombre, excluir_archivo=exclude.pk if exclude else None)

    def partial_update(self, request, *args, **kwargs):
        datos = _datos_mutacion_archivo(request, kwargs.get("pk"))
        with ServicioPapelera().proteger(**datos, eliminado=False) as archivo:
            nombre = _nombre(request.data.get("nombre"))
            if not nombre:
                return fail("VALIDATION_ERROR", {"nombre": ["El nombre del archivo es obligatorio."]})
            if not self._nombre_unico(nombre, archivo.carpeta_id, datos["organizacion_id"], archivo):
                return fail("VALIDATION_ERROR", {"nombre": ["Ya existe un archivo con ese nombre."]}, status=409)
            archivo.nombre = nombre
            archivo.save(update_fields=["nombre", "actualizado_en"])
            return ok(self.get_serializer(archivo).data)

    def destroy(self, request, *args, **kwargs):
        ServicioPapelera().enviar(**_datos_mutacion_archivo(request, kwargs.get("pk")))
        return ok({"mensaje": "El archivo se movió a la papelera."})

    @action(detail=True, methods=["post"])
    def mover(self, request, pk=None):
        datos = _datos_mutacion_archivo(request, pk)
        with ServicioPapelera().proteger(**datos, eliminado=False) as archivo:
            valor = request.data.get("carpeta_id")
            if valor in (None, "", "null"):
                carpeta = None
            else:
                identificador = _uuid(valor)
                carpeta = Carpeta.objects.filter(pk=identificador, organizacion_id=datos["organizacion_id"], en_papelera=False).first() if identificador else None
                if carpeta is None:
                    return fail("VALIDATION_ERROR", {"carpeta_id": ["La carpeta indicada no existe."]})
            if not self._nombre_unico(archivo.nombre, carpeta.pk if carpeta else None, datos["organizacion_id"], archivo):
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

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        contexto["ahora_papelera"] = timezone.now()
        return contexto

    def get_queryset(self):
        from rest_framework.exceptions import PermissionDenied
        from .permisos_papelera import LECTURA
        ambito = self._ambito()
        if ambito.nivel_rol not in (0, 3):
            raise PermissionDenied()
        qs = Archivo.objects.filter(organizacion_id=ambito.organizacion_id, en_papelera=True)
        if ambito.nivel_rol == 3:
            repo = RepositorioPapelera()
            ids = [a.pk for a in qs.iterator() if set(repo.permisos(
                self.request.user.pk, a, bloquear=False)) & LECTURA]
            qs = qs.filter(pk__in=ids)
        if getattr(getattr(self, "request", None), "query_params", {}).get("vista") == "raices":
            from auth_workspaces.models import LogAuditoria
            repo = RepositorioPapelera()
            duplicados = []
            raices_visibles = {}
            for archivo in qs.iterator():
                evento = repo.ultimo_evento(archivo)
                detalles = evento.detalles if evento else {}
                operacion = detalles.get("operacion_id") if isinstance(detalles, dict) else None
                if detalles.get("origen") != "CARPETA" or not operacion:
                    continue
                lote = LogAuditoria.objects.filter(
                    organizacion_id=ambito.organizacion_id,
                    accion="PAPELERA_CARPETA_ENVIADA",
                    detalles__version=1, detalles__operacion_id=operacion,
                    detalles__cerrado=True).first()
                if not lote or not isinstance(lote.detalles, dict):
                    continue
                raiz_id = lote.detalles.get("raiz_id")
                if not raiz_id:
                    continue
                activa = Carpeta.objects.filter(
                    pk=raiz_id, organizacion_id=ambito.organizacion_id,
                    en_papelera=True).exists()
                restaurada = LogAuditoria.objects.filter(
                    organizacion_id=ambito.organizacion_id,
                    accion="PAPELERA_CARPETA_RESTAURADA",
                    detalles__operacion_id=operacion).exists()
                visible = ambito.nivel_rol == 0
                if activa and not visible and raiz_id not in raices_visibles:
                    raiz = Carpeta.objects.filter(
                        pk=raiz_id, organizacion_id=ambito.organizacion_id,
                        en_papelera=True).first()
                    raices_visibles[raiz_id] = bool(raiz and set(repo.permisos(
                        self.request.user.pk, SimpleNamespace(
                            pk=None, carpeta_id=raiz.pk,
                            organizacion_id=ambito.organizacion_id), bloquear=False)) & LECTURA)
                    visible = raices_visibles[raiz_id]
                elif raiz_id in raices_visibles:
                    visible = raices_visibles[raiz_id]
                if activa and not restaurada and visible:
                    duplicados.append(archivo.pk)
            qs = qs.exclude(pk__in=duplicados)
        return qs.order_by(F('fecha_papelera').desc(nulls_last=True), 'id')

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        if not isinstance(request.data, Mapping) or set(request.data) - {'organizacion_id'}:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'non_field_errors':['Cuerpo de restauración no válido.']})
        ServicioPapelera().restaurar(**_datos_mutacion_archivo(request, pk))
        return ok({"mensaje": "El archivo se restauró correctamente."})

    def destroy(self, request, *args, **kwargs):
        datos = _datos_mutacion_archivo(request, kwargs.get("pk"))
        ServicioPapelera().purgar(
            **datos,
            crear_cliente=lambda: ClienteS3(ConfiguracionS3.desde_entorno()),
        )
        return Response(status=204)


class PapeleraCarpetasView(ContratoAPIMixin, APIView):
    """Extensión tipada; el listado antiguo de papelera sigue conteniendo archivos."""

    def get(self, request):
        from rest_framework.exceptions import PermissionDenied
        from .lotes_papelera import listar_raices_carpeta
        from .permisos_papelera import LECTURA

        ambito = resolver_organizacion(request.user, _organizacion_id(request))
        if ambito.nivel_rol not in (0, 3):
            raise PermissionDenied()
        elementos = listar_raices_carpeta(ambito.organizacion_id)
        if ambito.nivel_rol == 3:
            repo = RepositorioPapelera()
            permitidos = []
            for elemento in elementos:
                recurso = Carpeta.objects.filter(
                    pk=elemento["id"], organizacion_id=ambito.organizacion_id).first()
                if recurso and set(repo.permisos(request.user.pk, SimpleNamespace(
                        pk=None, carpeta_id=recurso.pk,
                        organizacion_id=ambito.organizacion_id), bloquear=False)) & LECTURA:
                    permitidos.append(elemento)
            elementos = permitidos
        for elemento in elementos:
            elemento["puede_purgar"] = ambito.nivel_rol == 0
        paginador = EnvelopePagination()
        pagina = paginador.paginate_queryset(elementos, request, view=self)
        respuesta = paginador.get_paginated_response(pagina)
        respuesta.data["data"]["puede_vaciar"] = ambito.nivel_rol == 0
        return respuesta


class RestaurarCarpetaPapeleraView(ContratoAPIMixin, APIView):
    def post(self, request, pk):
        ambito = _ambito_mutacion(request)
        from .lotes_papelera import ServicioLotesCarpeta
        ServicioLotesCarpeta().restaurar(
            solicitante_id=request.user.pk,
            organizacion_id=ambito.organizacion_id,
            carpeta_id=pk,
        )
        return ok({"mensaje": "La carpeta y sus elementos del lote se restauraron correctamente."})


class PurgarCarpetaPapeleraView(ContratoAPIMixin, APIView):
    def delete(self, request, pk):
        ambito = _ambito_mutacion(request)
        from .lotes_papelera import ServicioLotesCarpeta
        ServicioLotesCarpeta().purgar(
            solicitante_id=request.user.pk,
            organizacion_id=ambito.organizacion_id,
            carpeta_id=pk,
            crear_cliente=lambda: ClienteS3(ConfiguracionS3.desde_entorno()),
        )
        return Response(status=204)


class VaciadoPapeleraView(ContratoAPIMixin, APIView):
    def post(self, request):
        ambito = _ambito_mutacion(request)
        from .lotes_papelera import ServicioLotesCarpeta
        operacion = ServicioLotesCarpeta().vaciar(
            solicitante_id=request.user.pk,
            organizacion_id=ambito.organizacion_id,
            crear_cliente=lambda: ClienteS3(ConfiguracionS3.desde_entorno()),
        )
        return ok({"mensaje": "El vaciado terminó.", "operacion_id": operacion})


class OperacionVaciadoPapeleraView(ContratoAPIMixin, APIView):
    def _servicio(self, request, operacion_id):
        ambito = _ambito_mutacion(request)
        from .lotes_papelera import ServicioLotesCarpeta
        return ServicioLotesCarpeta(), ambito.organizacion_id

    def get(self, request, operacion_id):
        ambito = resolver_organizacion(request.user, _organizacion_id(request))
        from .lotes_papelera import ServicioLotesCarpeta
        estado = ServicioLotesCarpeta().estado_vaciado(
            solicitante_id=request.user.pk, organizacion_id=ambito.organizacion_id,
            operacion_id=operacion_id)
        return ok(estado)

    def post(self, request, operacion_id):
        servicio, org = self._servicio(request, operacion_id)
        operacion = servicio.vaciar(
            solicitante_id=request.user.pk, organizacion_id=org,
            operacion_id=operacion_id,
            crear_cliente=lambda: ClienteS3(ConfiguracionS3.desde_entorno()),
        )
        return ok({"mensaje": "El vaciado terminó.", "operacion_id": operacion})


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
