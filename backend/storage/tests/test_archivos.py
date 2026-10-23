import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_workspaces.models import Usuario
from common.testing import cliente_autenticado, espacio_de_trabajo

from storage.models import Archivo, Carpeta


class ArchivosAPITests(APITestCase):
    def setUp(self):
        self.usuario_id, self.organizacion_id = espacio_de_trabajo(nivel_rol=0)
        self.otro_usuario_id, self.otra_organizacion_id = espacio_de_trabajo(nivel_rol=0)
        self.usuario = Usuario.objects.get(pk=self.usuario_id)
        self.client = cliente_autenticado(self.usuario_id)

    def _url(self, nombre, *args, **params):
        base = reverse(nombre, args=args)
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base}?{query}" if query else base

    def _url_org(self, nombre, *args):
        return self._url(nombre, *args, organizacion_id=self.organizacion_id)

    def _crear_carpeta(self, organizacion_id=None, **kwargs):
        organizacion_id = organizacion_id or self.organizacion_id
        nombre = kwargs.get("nombre", "Carpeta")
        defaults = {
            "organizacion_id": organizacion_id,
            "nombre": nombre,
        }
        defaults.update(kwargs)
        return Carpeta.objects.create(**defaults)

    def _crear_archivo(self, organizacion_id=None, **kwargs):
        organizacion_id = organizacion_id or self.organizacion_id
        propietario = kwargs.pop("propietario", self.usuario)
        clave = kwargs.get("clave_s3") or f"clave-{uuid.uuid4()}"
        defaults = {
            "organizacion_id": organizacion_id,
            "propietario": propietario,
            "nombre": "archivo.txt",
            "clave_s3": clave,
            "tamano_bytes": 1024,
            "tipo_mime": "text/plain",
        }
        defaults.update(kwargs)
        return Archivo.objects.create(**defaults)

    def test_lista_requiere_auth(self):
        self.client.credentials()
        response = self.client.get(self._url_org("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detalle_requiere_auth(self):
        archivo = self._crear_archivo()
        self.client.credentials()
        response = self.client.get(self._url_org("archivo-detail", archivo.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_requiere_auth(self):
        archivo = self._crear_archivo()
        self.client.credentials()
        response = self.client.patch(
            self._url_org("archivo-detail", archivo.pk),
            {"nombre": "nuevo.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mover_requiere_auth(self):
        archivo = self._crear_archivo()
        self.client.credentials()
        response = self.client.post(
            self._url_org("archivo-mover", archivo.pk),
            {"carpeta_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_aislamiento_lista(self):
        self._crear_archivo(nombre="mio.txt")
        self._crear_archivo(organizacion_id=self.otra_organizacion_id, nombre="ajeno.txt")
        response = self.client.get(self._url_org("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"mio.txt"})

    def test_aislamiento_detalle_404(self):
        ajeno = self._crear_archivo(organizacion_id=self.otra_organizacion_id, nombre="ajeno.txt")
        response = self.client.get(self._url_org("archivo-detail", ajeno.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "NO_ENCONTRADO")

    def test_lista_excluye_papelera(self):
        self._crear_archivo(nombre="activo.txt")
        self._crear_archivo(nombre="basura.txt", en_papelera=True)
        response = self.client.get(self._url_org("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"activo.txt"})

    def test_filtro_carpeta(self):
        carpeta = self._crear_carpeta(nombre="Docs")
        self._crear_archivo(nombre="raiz.txt", carpeta=None)
        self._crear_archivo(nombre="en_docs.txt", carpeta=carpeta)

        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, carpeta_id="null")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"raiz.txt"})

        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, carpeta_id=str(carpeta.pk))
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"en_docs.txt"})

        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, carpeta="null")
        )
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"raiz.txt", "en_docs.txt"})

    def test_filtro_buscar(self):
        self._crear_archivo(nombre="contrato.pdf")
        self._crear_archivo(nombre="foto.png")
        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, buscar="cont")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"contrato.pdf"})

    def test_filtro_tipo(self):
        self._crear_archivo(nombre="doc.pdf")
        self._crear_archivo(nombre="sheet.xlsx")
        self._crear_archivo(nombre="readme")

        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, tipo="pdf")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"doc.pdf"})

        response = self.client.get(
            self._url("archivo-list", organizacion_id=self.organizacion_id, tipo="otro")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"readme"})

    def test_renombrar(self):
        archivo = self._crear_archivo(nombre="viejo.txt")
        response = self.client.patch(
            self._url_org("archivo-detail", archivo.pk),
            {"nombre": "nuevo.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["nombre"], "nuevo.txt")
        archivo.refresh_from_db()
        self.assertEqual(archivo.nombre, "nuevo.txt")

    def test_renombrar_duplicado_409(self):
        carpeta = self._crear_carpeta(nombre="Docs")
        self._crear_archivo(nombre="a.txt", carpeta=carpeta)
        archivo2 = self._crear_archivo(nombre="b.txt", carpeta=carpeta)
        response = self.client.patch(
            self._url_org("archivo-detail", archivo2.pk),
            {"nombre": "a.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_mover_a_carpeta(self):
        archivo = self._crear_archivo(nombre="mover.txt")
        carpeta = self._crear_carpeta(nombre="Destino")
        response = self.client.post(
            self._url_org("archivo-mover", archivo.pk),
            {"carpeta_id": str(carpeta.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["carpeta_id"], str(carpeta.pk))
        archivo.refresh_from_db()
        self.assertEqual(archivo.carpeta_id, carpeta.pk)

    def test_mover_a_raiz(self):
        carpeta = self._crear_carpeta(nombre="Origen")
        archivo = self._crear_archivo(nombre="raiz.txt", carpeta=carpeta)
        response = self.client.post(
            self._url_org("archivo-mover", archivo.pk),
            {"carpeta_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["carpeta_id"])
        archivo.refresh_from_db()
        self.assertIsNone(archivo.carpeta_id)

    def test_renombrar_nombre_vacio(self):
        archivo = self._crear_archivo(nombre="x.txt")
        response = self.client.patch(
            self._url_org("archivo-detail", archivo.pk),
            {"nombre": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_mover_rechaza_carpeta_inexistente(self):
        archivo = self._crear_archivo(nombre="x.txt")
        response = self.client.post(
            self._url_org("archivo-mover", archivo.pk),
            {"carpeta_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("carpeta_id", response.data["error"]["fields"])

    def test_mover_rechaza_carpeta_otra_organizacion(self):
        archivo = self._crear_archivo(nombre="x.txt")
        ajena = self._crear_carpeta(
            organizacion_id=self.otra_organizacion_id, nombre="Ajena"
        )
        response = self.client.post(
            self._url_org("archivo-mover", archivo.pk),
            {"carpeta_id": str(ajena.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("carpeta_id", response.data["error"]["fields"])

    def test_escritura_requerida_para_renombrar(self):
        uid, oid = espacio_de_trabajo(nivel_rol=1)
        usuario = Usuario.objects.get(pk=uid)
        cliente = cliente_autenticado(uid)
        archivo = self._crear_archivo(organizacion_id=oid, propietario=usuario)
        response = cliente.patch(
            self._url("archivo-detail", archivo.pk, organizacion_id=oid),
            {"nombre": "hackeado.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "SIN_PERMISO")
