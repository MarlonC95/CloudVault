"""Compartir archivos y carpetas como en Drive (contrato: API_CONTRACTS.md §6).

* Dueño (miembro con escritura en la organización del recurso): enlace único por recurso y
  permisos por usuario registrado.
* "Compartido conmigo" y vista previa para quien tiene acceso por membresía o por ACL.
* Acceso público por token del enlace; la sesión es opcional salvo para subir.
"""

import ipaddress
import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from almacenamiento.configuracion_inicio import cliente_firmador
from almacenamiento.contrato import CodigoError
from almacenamiento.errores import ErrorCarga, error_de_almacenamiento
from auth_workspaces.authentication import CloudVaultJWTAuthentication
from auth_workspaces.models import LogAuditoria, Usuario
from common.ambito import resolver_organizacion
from common.errores import manejar_error
from common.responses import ok
from storage.models import Archivo, Carpeta
from storage.servicios import ProveedorStorage

from .acceso import (acceso_usuario, dentro_del_enlace, enlace_vigente, es_compartida,
                     es_miembro, miembro_con_acceso_general, unirse)
from .models import ESCRITURA, LECTURA, EnlacePublico, PermisoRecurso

SALT_ACCESO = "compartir.acceso"
VIGENCIA_ACCESO = 900  # segundos de validez de X-Share-Token tras introducir la contraseña


def _uuid(valor, campo):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({campo: ["Identificador no válido."]}) from None


def _datos(request):
    if not isinstance(request.data, dict):
        raise ValidationError({"non_field_errors": ["Se requiere un objeto JSON."]})
    return request.data


def _filtro(recurso):
    return {"archivo": recurso} if isinstance(recurso, Archivo) else {"carpeta": recurso}


def _recurso_pedido(datos):
    """Archivo o carpeta (fuera de la papelera) indicado con exactamente uno de archivo_id/carpeta_id."""
    archivo_id, carpeta_id = datos.get("archivo_id") or None, datos.get("carpeta_id") or None
    if (archivo_id is None) == (carpeta_id is None):
        raise ValidationError({"non_field_errors": ["Indica archivo_id o carpeta_id (solo uno)."]})
    if archivo_id is not None:
        recurso = Archivo.objects.filter(pk=_uuid(archivo_id, "archivo_id"), en_papelera=False).first()
    else:
        recurso = Carpeta.objects.filter(pk=_uuid(carpeta_id, "carpeta_id"), en_papelera=False).first()
    if recurso is None:
        raise NotFound()
    return recurso


def _exigir_dueno(request, recurso):
    # Sin organización, resolver_organizacion caería en la única membresía del usuario.
    if recurso.organizacion_id is None:
        raise NotFound()
    ambito = resolver_organizacion(request.user, recurso.organizacion_id)
    if not ambito.es_admin:
        raise NotFound()


def _rol_y_descarga(datos, recurso, campo, rol, descarga):
    """Rol y descarga pedidos (o los dados si faltan). Subir solo en carpetas; escribir implica descargar."""
    rol, descarga = datos.get(campo, rol), datos.get("permite_descarga", descarga)
    if rol not in (LECTURA, ESCRITURA) or (rol == ESCRITURA and not isinstance(recurso, Carpeta)):
        raise ValidationError({campo: ["Rol no válido para este recurso."]})
    if not isinstance(descarga, bool):
        raise ValidationError({"permite_descarga": ["Debe ser true o false."]})
    return rol, descarga or rol == ESCRITURA


def _fecha_futura(valor):
    if valor in (None, ""):
        return None
    try:
        fecha = parse_datetime(valor) if isinstance(valor, str) else None
    except ValueError:
        fecha = None
    if fecha is not None and timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    if fecha is None or fecha <= timezone.now():
        raise ValidationError({"fecha_expiracion": ["Debe ser una fecha futura (ISO 8601) o null."]})
    return fecha


def _auditar(request, accion, organizacion_id, **detalles):
    try:
        ip = str(ipaddress.ip_address(request.META.get("REMOTE_ADDR")))
    except ValueError:
        ip = None
    LogAuditoria.objects.create(
        usuario_id=request.user.pk if request.user.is_authenticated else None,
        organizacion_id=organizacion_id, accion=accion, ip_origen=ip,
        detalles={k: str(v) if isinstance(v, UUID) else v for k, v in detalles.items()})


def _efectivo(permiso):
    """(rol, descarga) vigentes de un permiso: los del enlace si vino por enlace; None si caducó."""
    enlace = permiso.enlace
    if enlace is None:
        rol, descarga = permiso.tipo_permiso, permiso.permite_descarga
    elif enlace.fecha_expiracion and enlace.fecha_expiracion <= timezone.now():
        return None
    else:
        rol, descarga = enlace.rol, enlace.permite_descarga
    return rol, descarga or rol == ESCRITURA


def _enlace(e):
    return {"id": e.pk, "token": e.token, "archivo_id": e.archivo_id, "carpeta_id": e.carpeta_id,
            "rol": e.rol, "permite_descarga": e.permite_descarga, "requiere_password": bool(e.contrasena_hash),
            "fecha_expiracion": e.fecha_expiracion, "fecha_creacion": e.fecha_creacion}


def _permiso(p):
    rol, descarga = _efectivo(p) or (p.enlace.rol, p.enlace.permite_descarga)
    return {"id": p.pk, "usuario": {"id": p.usuario_id, "correo": p.usuario.correo_electronico,
                                    "nombre": p.usuario.nombre_completo},
            "tipo_permiso": rol, "permite_descarga": descarga, "via_enlace": p.enlace_id is not None,
            "fecha_creacion": p.fecha_creacion}


def _contenido(carpeta):
    ambito = {"organizacion_id": carpeta.organizacion_id, "en_papelera": False}
    carpetas = Carpeta.objects.filter(padre_id=carpeta.pk, **ambito).order_by("nombre")
    archivos = Archivo.objects.filter(carpeta_id=carpeta.pk, **ambito).order_by("nombre")
    return {"carpetas": [{"id": c.pk, "nombre": c.nombre} for c in carpetas],
            "archivos": [{"id": a.pk, "nombre": a.nombre, "tamano_bytes": a.tamano_bytes,
                          "tipo_mime": a.tipo_mime, "fecha_modificacion": a.actualizado_en} for a in archivos]}


def _url_temporal(archivo, *, descargar):
    cliente = cliente_firmador()
    try:
        firma = (cliente.firmar_descarga(archivo.clave_s3, archivo.nombre) if descargar
                 else cliente.firmar_get(archivo.clave_s3))
    except ValueError:  # clave o nombre no firmables
        raise ErrorCarga(CodigoError.SERVICE_UNAVAILABLE) from None
    finally:
        cliente.cerrar()
    return {"url_descarga" if descargar else "url_vista_previa": firma.url, "expira_en": firma.expira_en,
            "nombre": archivo.nombre, "tipo": archivo.tipo_mime}


def _puede_subir(usuario, carpeta_id):
    if not usuario.is_authenticated or carpeta_id is None:
        return False
    try:
        ProveedorStorage().resolver_destino(solicitante_id=usuario.pk, carpeta_id=carpeta_id)
    except (NotFound, PermissionDenied, ErrorCarga):
        return False
    return True


class Base(APIView):
    def get_exception_handler(self):
        return lambda exc, context: (error_de_almacenamiento(exc, context) if isinstance(exc, ErrorCarga)
                                     else manejar_error(exc, context))


# --- Dueño ---------------------------------------------------------------------------------

class EnlacesView(Base):
    def get(self, request):
        recurso = _recurso_pedido(request.query_params)
        _exigir_dueno(request, recurso)
        enlace = EnlacePublico.objects.filter(**_filtro(recurso)).first()
        return ok(_enlace(enlace) if enlace else None)

    def post(self, request):
        """Crea o reemplaza la configuración del enlace del recurso; ``password`` ausente la conserva."""
        datos = _datos(request)
        recurso = _recurso_pedido(datos)
        _exigir_dueno(request, recurso)
        rol, descarga = _rol_y_descarga(datos, recurso, "rol", LECTURA, False)
        expiracion = _fecha_futura(datos.get("fecha_expiracion"))
        enlace = EnlacePublico.objects.filter(**_filtro(recurso)).first()
        nuevo = enlace is None
        if nuevo:
            enlace = EnlacePublico(token=secrets.token_urlsafe(32), creado_por_id=request.user.pk, **_filtro(recurso))
        enlace.rol, enlace.permite_descarga, enlace.fecha_expiracion = rol, descarga, expiracion
        if "password" in datos:
            password = datos["password"]
            if password in (None, ""):
                enlace.contrasena_hash = None
            elif isinstance(password, str) and len(password) <= 128:
                enlace.contrasena_hash = make_password(password)
            else:
                raise ValidationError({"password": ["Texto de hasta 128 caracteres, o null para quitarla."]})
        # ponytail: dos POST simultáneos del primer enlace chocan con ux_enlace_* (500 en el segundo);
        # reintentar como actualización si llega a pasar.
        enlace.save(force_insert=nuevo)
        _auditar(request, "ENLACE_CREADO" if nuevo else "ENLACE_ACTUALIZADO", recurso.organizacion_id,
                 enlace_id=enlace.pk, rol=rol, permite_descarga=descarga)
        return ok(_enlace(enlace), status=201 if nuevo else 200)


class EnlaceDetalleView(Base):
    def delete(self, request, pk):
        enlace = EnlacePublico.objects.select_related("archivo", "carpeta").filter(pk=pk).first()
        if enlace is None:
            raise NotFound()
        _exigir_dueno(request, enlace.recurso)
        enlace.delete()  # Los permisos obtenidos por el enlace caen en cascada.
        _auditar(request, "ENLACE_REVOCADO", enlace.recurso.organizacion_id, enlace_id=pk)
        return Response(status=204)


class PermisosView(Base):
    def get(self, request):
        recurso = _recurso_pedido(request.query_params)
        _exigir_dueno(request, recurso)
        permisos = (PermisoRecurso.objects.select_related("usuario", "enlace")
                    .filter(**_filtro(recurso)).order_by("fecha_creacion", "id"))
        return ok([_permiso(p) for p in permisos])

    def post(self, request):
        datos = _datos(request)
        recurso = _recurso_pedido(datos)
        _exigir_dueno(request, recurso)
        rol, descarga = _rol_y_descarga(datos, recurso, "tipo_permiso", LECTURA, True)
        correo = datos.get("correo")
        usuario = (Usuario.objects.filter(correo_electronico__iexact=correo.strip(), is_active=True).first()
                   if isinstance(correo, str) and correo.strip() else None)
        if usuario is None or (es_miembro(usuario.pk, recurso.organizacion_id)
                               and not es_compartida(recurso.organizacion_id)):
            raise ValidationError({"correo": ["No hay una cuenta activa disponible con ese correo."]})
        permiso, creado = PermisoRecurso.objects.update_or_create(
            usuario=usuario, **_filtro(recurso),
            defaults={"tipo_permiso": rol, "permite_descarga": descarga, "enlace": None})
        _auditar(request, "PERMISO_OTORGADO", recurso.organizacion_id, permiso_id=permiso.pk,
                 usuario_destino=usuario.pk, tipo_permiso=rol, permite_descarga=descarga)
        return ok(_permiso(permiso), status=201 if creado else 200)


class PermisoDetalleView(Base):
    def _cargar(self, request, pk):
        permiso = (PermisoRecurso.objects.select_related("usuario", "enlace", "archivo", "carpeta")
                   .filter(pk=pk).first())
        if permiso is None:
            raise NotFound()
        recurso = permiso.archivo or permiso.carpeta
        _exigir_dueno(request, recurso)
        return permiso, recurso

    def patch(self, request, pk):
        """Ajusta el permiso; uno obtenido por enlace pasa a ser directo (sobrevive al enlace)."""
        permiso, recurso = self._cargar(request, pk)
        actual = _efectivo(permiso) or (permiso.tipo_permiso, permiso.permite_descarga)
        rol, descarga = _rol_y_descarga(_datos(request), recurso, "tipo_permiso", *actual)
        permiso.tipo_permiso, permiso.permite_descarga, permiso.enlace = rol, descarga, None
        permiso.save(update_fields=["tipo_permiso", "permite_descarga", "enlace"])
        _auditar(request, "PERMISO_ACTUALIZADO", recurso.organizacion_id, permiso_id=permiso.pk,
                 tipo_permiso=rol, permite_descarga=descarga)
        return ok(_permiso(permiso))

    def delete(self, request, pk):
        permiso, recurso = self._cargar(request, pk)
        permiso.delete()
        _auditar(request, "PERMISO_REVOCADO", recurso.organizacion_id, permiso_id=pk,
                 usuario_destino=permiso.usuario_id)
        return Response(status=204)


# --- Compartido conmigo y vista previa -------------------------------------------------------

class CompartidosView(Base):
    def get(self, request):
        items = []
        permisos = (PermisoRecurso.objects.select_related("archivo", "carpeta", "enlace")
                    .filter(usuario_id=request.user.pk).order_by("-fecha_creacion"))
        for p in permisos:
            efectivo, recurso = _efectivo(p), p.archivo or p.carpeta
            if efectivo is None or recurso.en_papelera:
                continue
            es_archivo = isinstance(recurso, Archivo)
            items.append({"tipo": "archivo" if es_archivo else "carpeta", "id": recurso.pk, "nombre": recurso.nombre,
                          "rol": efectivo[0], "permite_descarga": efectivo[1],
                          "tamano_bytes": recurso.tamano_bytes if es_archivo else None,
                          "tipo_mime": recurso.tipo_mime if es_archivo else None})
        return ok(items)


class ContenidoCompartidoView(Base):
    def get(self, request, pk):
        acceso = acceso_usuario(request.user.pk, carpeta_id=pk)
        if acceso is None:
            raise NotFound()
        carpeta = Carpeta.objects.select_related("padre").get(pk=pk)
        padre = carpeta.padre
        padre_id = (padre.pk if padre and padre.organizacion_id == carpeta.organizacion_id
                    and acceso_usuario(request.user.pk, carpeta_id=padre.pk) else None)
        return ok({"carpeta": {"id": carpeta.pk, "nombre": carpeta.nombre, "padre_id": padre_id},
                   "rol": acceso.rol, "permite_descarga": acceso.permite_descarga,
                   "puede_subir": acceso.rol == ESCRITURA and _puede_subir(request.user, carpeta.pk),
                   **_contenido(carpeta)})


class VistaPreviaView(Base):
    def get(self, request, pk):
        archivo = Archivo.objects.filter(pk=pk, en_papelera=False).first()
        if archivo is None or not (
            miembro_con_acceso_general(request.user.pk, archivo.organizacion_id)
            or (archivo.propietario_id == request.user.pk and es_miembro(request.user.pk, archivo.organizacion_id))
            or acceso_usuario(request.user.pk, archivo_id=pk)
        ):
            raise NotFound()
        return ok(_url_temporal(archivo, descargar=False))


# --- Público por token -----------------------------------------------------------------------

class JWTOpcional(CloudVaultJWTAuthentication):
    """Una sesión caducada no impide abrir un enlace público: se trata como anónima."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None


class PublicoThrottle(SimpleRateThrottle):
    scope = "compartir_publico"

    def get_rate(self):
        return settings.COMPARTIR_PUBLICO_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PasswordThrottle(SimpleRateThrottle):
    scope = "compartir_password"

    def get_rate(self):
        return settings.COMPARTIR_PASSWORD_RATE

    def get_cache_key(self, request, view):
        token = sha256(str(view.kwargs.get("token")).encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{token}"}


def _huella(enlace):
    # Cambiar o quitar la contraseña invalida los X-Share-Token ya emitidos.
    return sha256(enlace.contrasena_hash.encode("utf-8")).hexdigest()[:16]


class PublicoBase(Base):
    authentication_classes = [JWTOpcional]
    permission_classes = [AllowAny]
    throttle_classes = [PublicoThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @staticmethod
    def verificado(request, enlace):
        """Un enlace protegido solo se abre con su comprobante de contraseña."""
        if not enlace.contrasena_hash:
            return True
        try:
            datos = signing.loads(request.headers.get("X-Share-Token", ""), salt=SALT_ACCESO,
                                  max_age=VIGENCIA_ACCESO)
        except signing.BadSignature:
            return False
        return datos == [enlace.token, _huella(enlace)]

    def enlace_verificado(self, request, token):
        enlace = enlace_vigente(token)
        if not self.verificado(request, enlace):
            raise PermissionDenied()
        return enlace


class PublicoView(PublicoBase):
    def get(self, request, token):
        enlace = enlace_vigente(token)
        tipo = "carpeta" if enlace.carpeta_id else "archivo"
        if not self.verificado(request, enlace):
            return ok({"tipo": tipo, "requiere_password": True})
        recurso = enlace.recurso
        datos = {"tipo": tipo, "id": recurso.pk, "nombre": recurso.nombre, "rol": enlace.rol,
                 "permite_descarga": enlace.permite_descarga, "requiere_password": bool(enlace.contrasena_hash),
                 "unido": request.user.is_authenticated and unirse(enlace, request.user.pk),
                 "puede_subir": _puede_subir(request.user, enlace.carpeta_id)}
        if tipo == "archivo":
            datos.update(tamano_bytes=recurso.tamano_bytes, tipo_mime=recurso.tipo_mime)
        return ok(datos)


class AccesoPublicoView(PublicoBase):
    throttle_classes = [PublicoThrottle, PasswordThrottle]

    def post(self, request, token):
        enlace = enlace_vigente(token)
        password = _datos(request).get("password")
        if (not enlace.contrasena_hash or not isinstance(password, str)
                or not check_password(password, enlace.contrasena_hash)):
            raise PermissionDenied()
        if request.user.is_authenticated:
            unirse(enlace, request.user.pk)
        return ok({"share_token": signing.dumps([enlace.token, _huella(enlace)], salt=SALT_ACCESO),
                   "expira_en": timezone.now() + timedelta(seconds=VIGENCIA_ACCESO)})


class ContenidoPublicoView(PublicoBase):
    def get(self, request, token):
        enlace = self.enlace_verificado(request, token)
        if enlace.carpeta_id is None:
            raise NotFound()
        pedida = request.query_params.get("carpeta_id") or None
        carpeta_id = enlace.carpeta_id if pedida is None else _uuid(pedida, "carpeta_id")
        if not dentro_del_enlace(enlace, carpeta_id=carpeta_id):
            raise NotFound()
        carpeta = Carpeta.objects.get(pk=carpeta_id)
        padre_id = None if carpeta.pk == enlace.carpeta_id else carpeta.padre_id
        return ok({"carpeta": {"id": carpeta.pk, "nombre": carpeta.nombre, "padre_id": padre_id},
                   "rol": enlace.rol, "permite_descarga": enlace.permite_descarga, **_contenido(carpeta)})


class ArchivoPublicoView(PublicoBase):
    def get(self, request, token, pk):
        enlace = self.enlace_verificado(request, token)
        archivo = Archivo.objects.filter(pk=pk).first()
        if archivo is None or not dentro_del_enlace(enlace, archivo=archivo):
            raise NotFound()
        accion = request.query_params.get("accion", "ver")
        if accion not in ("ver", "descargar"):
            raise ValidationError({"accion": ["Usa ver o descargar."]})
        # ponytail: "solo ver" se aplica en la interfaz y en esta ruta; la URL temporal de lectura
        # sigue permitiendo guardar el contenido mientras vive (igual que una vista previa de Drive).
        if accion == "descargar" and not enlace.permite_descarga:
            raise PermissionDenied()
        datos = _url_temporal(archivo, descargar=accion == "descargar")
        if accion == "descargar":
            _auditar(request, "DESCARGA_ENLACE", archivo.organizacion_id, enlace_id=enlace.pk, archivo_id=archivo.pk)
        return ok(datos)
