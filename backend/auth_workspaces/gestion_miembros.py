"""Mutaciones internas sobre membresías existentes; sin cambios de esquema."""
from uuid import UUID
from django.db import connections
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

class PropietarioProtegido(APIException):
    status_code = 409
    default_code = "OWNER_REQUIRED"
    default_detail = "El propietario no puede modificarse ni retirarse."
from subscriptions.models import MiembroOrganizacion
from .models import Usuario, LogAuditoria

ROLES = {"LECTOR_NV1": 1, "OPERATIVO_NV2": 2, "AVANZADO_NV3": 3}


def uuid_entrada(valor, campo):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({campo: ["Debe ser un UUID válido."]}) from exc


class RepositorioMiembros:
    def transaccion(self, org):
        from almacenamiento.persistencia import RepositorioCargas
        return RepositorioCargas().unidad_de_trabajo(organizacion_id=org)

    def autorizar(self, actor, org):
        cuenta = Usuario.objects.select_for_update().filter(pk=actor, is_active=True, is_2fa_enabled=False).first()
        if cuenta is None:
            raise PermissionDenied()
        miembro = self.objetivo(actor, org)
        if miembro is None:
            raise NotFound()
        propietarios = list(MiembroOrganizacion.objects.select_for_update().filter(organizacion_id=org, nivel_rol=0).values_list("usuario_id", flat=True))
        if propietarios != [actor]:
            raise PermissionDenied()
        if type(miembro.nivel_rol) is not int or miembro.nivel_rol != 0:
            raise PermissionDenied()

    def objetivo(self, usuario, org):
        return MiembroOrganizacion.objects.select_for_update().filter(usuario_id=usuario, organizacion_id=org).first()

    def cambiar(self, miembro, nivel):
        miembro.nivel_rol = nivel
        miembro.save(update_fields=["nivel_rol"])

    def retirar(self, miembro, org):
        # Eliminar únicamente concesiones sobre recursos de esta organización.
        # No tocar cuenta, archivos, carpetas, otras membresías ni enlaces públicos.
        with connections["default"].cursor() as cursor:
            cursor.execute("""DELETE FROM permisos_recurso p WHERE p.usuario_id = %s AND (
                EXISTS (SELECT 1 FROM archivos a WHERE a.id=p.archivo_id AND a.organizacion_id=%s)
                OR EXISTS (SELECT 1 FROM carpetas c WHERE c.id=p.carpeta_id AND c.organizacion_id=%s))""",
                [miembro.usuario_id, org, org])
        miembro.delete()

    def auditar(self, actor, org, objetivo, accion, anterior, nuevo):
        LogAuditoria.objects.create(usuario_id=actor, organizacion_id=org, accion=accion,
            fecha_evento=timezone.now(), detalles={"version": 1, "usuario_afectado_id": str(objetivo),
            "nivel_anterior": anterior, "nivel_nuevo": nuevo})


class ServicioMiembros:
    def __init__(self, repo=None):
        self.repo = repo if repo is not None else RepositorioMiembros()

    def ejecutar(self, actor, organizacion, usuario, *, rol=None, retirar=False):
        org = uuid_entrada(organizacion, "organizacion_id")
        objetivo = uuid_entrada(usuario, "usuario_id")
        if not retirar and rol == "PROPIETARIO":
            raise PropietarioProtegido()
        if not retirar and (not isinstance(rol, str) or rol not in ROLES):
            raise ValidationError({"rol": ["Use LECTOR_NV1, OPERATIVO_NV2 o AVANZADO_NV3."]})
        with self.repo.transaccion(org):
            self.repo.autorizar(actor, org)
            miembro = self.repo.objetivo(objetivo, org)
            if miembro is None:
                if retirar:
                    return False
                raise NotFound()
            anterior = miembro.nivel_rol
            if type(anterior) is not int or anterior not in (1, 2, 3):
                raise PropietarioProtegido()
            nuevo = None if retirar else ROLES[rol]
            if anterior == nuevo:
                return False
            if retirar:
                self.repo.retirar(miembro, org)
            else:
                self.repo.cambiar(miembro, nuevo)
            self.repo.auditar(actor, org, objetivo,
                "MEMBER_REMOVED" if retirar else "MEMBER_ROLE_CHANGED", anterior, nuevo)
            return True
