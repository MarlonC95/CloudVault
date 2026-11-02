from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from almacenamiento.errores import ErrorCarga
from almacenamiento.s3 import FirmaS3
from common.testing import agregar_miembro, cliente_autenticado, crear_usuario, espacio_de_trabajo
from compartir.acceso import acceso_usuario
from compartir.models import EnlacePublico, PermisoRecurso
from storage.models import Archivo, Carpeta
from storage.servicios import ProveedorStorage

API = "/api/v1/"


class FirmadorFalso:
    def firmar_get(self, clave, *, vigencia=None):
        return FirmaS3(f"https://s3.test/{clave}?ver", "GET", {}, timezone.now() + timedelta(minutes=5))

    def firmar_descarga(self, clave, nombre, *, vigencia=None, version=None):
        return FirmaS3(f"https://s3.test/{clave}?bajar", "GET", {}, timezone.now() + timedelta(minutes=5))

    def cerrar(self):
        pass


@mock.patch("compartir.views.cliente_firmador", FirmadorFalso)
class CompartirTests(TestCase):
    def setUp(self):
        cache.clear()
        self.dueno, self.org = espacio_de_trabajo()
        self.cliente = cliente_autenticado(self.dueno)
        self.raiz = Carpeta.objects.create(organizacion_id=self.org, nombre="Equipo")
        self.sub = Carpeta.objects.create(organizacion_id=self.org, padre=self.raiz, nombre="Sub")
        self.fuera = Carpeta.objects.create(organizacion_id=self.org, nombre="Privada")
        self.archivo = self._archivo(self.sub, "informe.pdf")
        self.privado = self._archivo(self.fuera, "secreto.pdf")
        self.invitado = crear_usuario(correo="invitado@example.test", nombre="Invitado")

    def _archivo(self, carpeta, nombre):
        return Archivo.objects.create(organizacion_id=self.org, carpeta=carpeta, propietario_id=self.dueno,
                                      nombre=nombre, clave_s3=f"cloudvault/dani/publicaciones/{uuid4()}",
                                      tamano_bytes=10, tipo_mime="application/pdf")

    def _enlace(self, **datos):
        r = self.cliente.post(API + "enlaces-compartidos/", datos, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        return r.json()["data"]

    def test_enlace_unico_por_recurso_y_reglas_de_rol(self):
        creado = self._enlace(carpeta_id=str(self.raiz.pk), rol="ESCRITURA")
        self.assertTrue(creado["permite_descarga"])  # escribir implica descargar
        r = self.cliente.post(API + "enlaces-compartidos/", {"carpeta_id": str(self.raiz.pk)}, format="json")
        self.assertEqual((r.status_code, r.json()["data"]["token"]), (200, creado["token"]))
        self.assertEqual(r.json()["data"]["rol"], "LECTURA")
        r = self.cliente.post(API + "enlaces-compartidos/", {"archivo_id": str(self.archivo.pk), "rol": "ESCRITURA"},
                              format="json")
        self.assertEqual(r.status_code, 400)
        r = cliente_autenticado(self.invitado).get(API + "enlaces-compartidos/", {"carpeta_id": str(self.raiz.pk)})
        self.assertEqual(r.status_code, 404)

    def test_enlace_publico_de_carpeta_limita_el_subarbol(self):
        token = self._enlace(carpeta_id=str(self.raiz.pk))["token"]
        anonimo = APIClient()
        r = anonimo.get(f"{API}publico/{token}/")
        self.assertEqual((r.status_code, r.json()["data"]["tipo"], r.json()["data"]["puede_subir"]),
                         (200, "carpeta", False))
        self.assertEqual(r["Cache-Control"], "no-store")
        r = anonimo.get(f"{API}publico/{token}/contenido/", {"carpeta_id": str(self.sub.pk)})
        self.assertEqual([a["nombre"] for a in r.json()["data"]["archivos"]], ["informe.pdf"])
        self.assertEqual(anonimo.get(f"{API}publico/{token}/contenido/",
                                     {"carpeta_id": str(self.fuera.pk)}).status_code, 404)
        self.assertEqual(anonimo.get(f"{API}publico/{token}/archivos/{self.privado.pk}/").status_code, 404)
        r = anonimo.get(f"{API}publico/{token}/archivos/{self.archivo.pk}/")
        self.assertIn("?ver", r.json()["data"]["url_vista_previa"])
        # Solo ver: la descarga se rechaza.
        r = anonimo.get(f"{API}publico/{token}/archivos/{self.archivo.pk}/", {"accion": "descargar"})
        self.assertEqual(r.status_code, 403)

    def test_contrasena_y_share_token(self):
        token = self._enlace(archivo_id=str(self.archivo.pk), permite_descarga=True, password="clave-1")["token"]
        anonimo = APIClient()
        self.assertEqual(anonimo.get(f"{API}publico/{token}/").json()["data"],
                         {"tipo": "archivo", "requiere_password": True})
        self.assertEqual(anonimo.get(f"{API}publico/{token}/archivos/{self.archivo.pk}/").status_code, 403)
        self.assertEqual(anonimo.post(f"{API}publico/{token}/acceso/", {"password": "mala"},
                                      format="json").status_code, 403)
        share = anonimo.post(f"{API}publico/{token}/acceso/", {"password": "clave-1"},
                             format="json").json()["data"]["share_token"]
        r = anonimo.get(f"{API}publico/{token}/archivos/{self.archivo.pk}/", {"accion": "descargar"},
                        HTTP_X_SHARE_TOKEN=share)
        self.assertIn("?bajar", r.json()["data"]["url_descarga"])
        # Cambiar la contraseña invalida los share tokens emitidos; omitirla la conserva.
        self._enlace(archivo_id=str(self.archivo.pk), password="clave-2")
        self.assertEqual(anonimo.get(f"{API}publico/{token}/archivos/{self.archivo.pk}/",
                                     HTTP_X_SHARE_TOKEN=share).status_code, 403)
        self.assertTrue(self._enlace(archivo_id=str(self.archivo.pk))["requiere_password"])

    def test_enlace_caducado_es_404(self):
        token = self._enlace(archivo_id=str(self.archivo.pk))["token"]
        EnlacePublico.objects.filter(token=token).update(fecha_expiracion=timezone.now() - timedelta(minutes=1))
        self.assertEqual(APIClient().get(f"{API}publico/{token}/").status_code, 404)

    def test_abrir_enlace_de_escritura_con_sesion_permite_subir_y_revocar_lo_quita(self):
        enlace = self._enlace(carpeta_id=str(self.raiz.pk), rol="ESCRITURA")
        invitado = cliente_autenticado(self.invitado)
        r = invitado.get(f"{API}publico/{enlace['token']}/")
        self.assertTrue(r.json()["data"]["unido"] and r.json()["data"]["puede_subir"])
        compartidos = invitado.get(API + "compartidos-conmigo/").json()["data"]
        self.assertEqual([(c["tipo"], c["rol"]) for c in compartidos], [("carpeta", "ESCRITURA")])
        # La subida se imputa a la organización (y cuota) del dueño.
        destino = ProveedorStorage().resolver_destino(solicitante_id=self.invitado, carpeta_id=self.sub.pk)
        self.assertEqual(destino.organizacion_id, self.org)
        r = invitado.get(f"{API}compartidos-conmigo/carpetas/{self.sub.pk}/contenido/")
        self.assertEqual((r.json()["data"]["carpeta"]["padre_id"], r.json()["data"]["puede_subir"]),
                         (str(self.raiz.pk), True))

        self.assertEqual(self.cliente.delete(f"{API}enlaces-compartidos/{enlace['id']}/").status_code, 204)
        self.assertEqual(invitado.get(API + "compartidos-conmigo/").json()["data"], [])
        with self.assertRaises(PermissionDenied):
            ProveedorStorage().resolver_destino(solicitante_id=self.invitado, carpeta_id=self.sub.pk)

    def test_permiso_directo_por_correo_y_descarga(self):
        r = self.cliente.post(API + "permisos-recurso/", {"carpeta_id": str(self.raiz.pk),
                              "correo": "INVITADO@example.test", "permite_descarga": False}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        permiso_id = r.json()["data"]["id"]
        # Heredado en el subárbol, no fuera de él.
        self.assertEqual(acceso_usuario(self.invitado, archivo_id=self.archivo.pk).rol, "LECTURA")
        self.assertIsNone(acceso_usuario(self.invitado, archivo_id=self.privado.pk))
        invitado = cliente_autenticado(self.invitado)
        self.assertEqual(invitado.get(f"{API}archivos/{self.archivo.pk}/vista-previa/").status_code, 200)
        self.assertEqual(invitado.get(f"{API}archivos/{self.privado.pk}/vista-previa/").status_code, 404)
        proveedor = ProveedorStorage()
        with self.assertRaises(ErrorCarga) as ctx:
            proveedor.autorizar_descarga(solicitante_id=self.invitado, archivo_id=self.archivo.pk)
        self.assertEqual(ctx.exception.status_code, 403)

        r = self.cliente.patch(f"{API}permisos-recurso/{permiso_id}/", {"permite_descarga": True}, format="json")
        self.assertTrue(r.json()["data"]["permite_descarga"])
        proveedor.autorizar_descarga(solicitante_id=self.invitado, archivo_id=self.archivo.pk)
        self.assertEqual(self.cliente.delete(f"{API}permisos-recurso/{permiso_id}/").status_code, 204)
        self.assertFalse(PermisoRecurso.objects.filter(pk=permiso_id).exists())

    def test_no_se_comparte_con_miembros_ni_correos_desconocidos(self):
        agregar_miembro(self.org, self.invitado, 1)
        for correo in ("invitado@example.test", "nadie@example.test"):
            r = self.cliente.post(API + "permisos-recurso/", {"archivo_id": str(self.archivo.pk), "correo": correo},
                                  format="json")
            self.assertEqual(r.status_code, 400, correo)
