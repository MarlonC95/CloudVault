from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_workspaces.models import Usuario
from common.testing import cliente_autenticado, espacio_de_trabajo

from storage.models import Archivo, Carpeta


class CarpetasAPITests(APITestCase):
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
        clave = kwargs.get("clave_s3") or f"clave-{Archivo.objects.count()}"
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
        response = self.client.get(self._url_org("carpeta-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_crear_requiere_escritura(self):
        uid, oid = espacio_de_trabajo(nivel_rol=1)
        cliente = cliente_autenticado(uid)
        response = cliente.post(
            self._url("carpeta-list", organizacion_id=oid),
            {"nombre": "Docs"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "SIN_PERMISO")

    def test_aislamiento_lista(self):
        self._crear_carpeta(nombre="Mia")
        self._crear_carpeta(organizacion_id=self.otra_organizacion_id, nombre="Ajena")
        response = self.client.get(self._url_org("carpeta-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {c["nombre"] for c in response.data["data"]["results"]}
        self.assertEqual(nombres, {"Mia"})

    def test_aislamiento_detalle_404(self):
        ajena = self._crear_carpeta(organizacion_id=self.otra_organizacion_id, nombre="Ajena")
        response = self.client.get(self._url_org("carpeta-detail", ajena.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "NO_ENCONTRADO")

    def test_nombre_repetido_409(self):
        self._crear_carpeta(nombre="Docs")
        response = self.client.post(
            self._url_org("carpeta-list"), {"nombre": "Docs"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_nombre_vacio_400(self):
        response = self.client.post(
            self._url_org("carpeta-list"), {"nombre": "  "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_crear_calcula_ruta(self):
        response = self.client.post(
            self._url_org("carpeta-list"), {"nombre": "Documentos"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["ruta_completa"], "/Documentos")
        self.assertIsNone(response.data["data"]["padre_id"])
        self.assertEqual(response.data["data"]["organizacion_id"], str(self.organizacion_id))

    def test_crear_subcarpeta(self):
        padre = self._crear_carpeta(nombre="Padre")
        response = self.client.post(
            self._url_org("carpeta-list"),
            {"nombre": "Hija", "padre_id": str(padre.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["ruta_completa"], "/Padre/Hija")
        self.assertEqual(response.data["data"]["padre_id"], str(padre.pk))

    def test_filtro_carpeta_padre(self):
        raiz = self._crear_carpeta(nombre="Raiz")
        self._crear_carpeta(padre=raiz, nombre="Hija")
        response = self.client.get(
            self._url("carpeta-list", organizacion_id=self.organizacion_id, padre="null")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {c["nombre"] for c in response.data["data"]["results"]}
        self.assertEqual(nombres, {"Raiz"})

    def test_buscar_carpetas(self):
        self._crear_carpeta(nombre="Facturas")
        self._crear_carpeta(nombre="Fotos")
        response = self.client.get(
            self._url("carpeta-list", organizacion_id=self.organizacion_id, buscar="Fact")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {c["nombre"] for c in response.data["data"]["results"]}
        self.assertEqual(nombres, {"Facturas"})

    def test_renombrar_actualiza_ruta(self):
        raiz = self._crear_carpeta(nombre="Raiz")
        hija = self._crear_carpeta(padre=raiz, nombre="Hija")
        response = self.client.patch(
            self._url_org("carpeta-detail", raiz.pk),
            {"nombre": "NuevaRaiz"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["ruta_completa"], "/NuevaRaiz")
        hija.refresh_from_db()
        self.assertEqual(hija.ruta_completa, "/NuevaRaiz/Hija")

    def test_mover_a_raiz_actualiza_rutas(self):
        raiz = self._crear_carpeta(nombre="Raiz")
        hija = self._crear_carpeta(padre=raiz, nombre="Hija")
        nieto = self._crear_carpeta(padre=hija, nombre="Nieto")
        response = self.client.post(
            self._url_org("carpeta-mover", hija.pk),
            {"padre_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        hija.refresh_from_db()
        nieto.refresh_from_db()
        self.assertIsNone(hija.padre_id)
        self.assertEqual(hija.ruta_completa, "/Hija")
        self.assertEqual(nieto.ruta_completa, "/Hija/Nieto")

    def test_mover_rechaza_ciclo(self):
        raiz = self._crear_carpeta(nombre="Raiz")
        hija = self._crear_carpeta(padre=raiz, nombre="Hija")
        nieto = self._crear_carpeta(padre=hija, nombre="Nieto")
        response = self.client.post(
            self._url_org("carpeta-mover", raiz.pk),
            {"padre_id": str(nieto.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_mover_rechaza_si_mismo(self):
        carpeta = self._crear_carpeta(nombre="Sola")
        response = self.client.post(
            self._url_org("carpeta-mover", carpeta.pk),
            {"padre_id": str(carpeta.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_mover_duplicado_409(self):
        raiz = self._crear_carpeta(nombre="Raiz")
        self._crear_carpeta(nombre="Hija")
        hija_de_raiz = self._crear_carpeta(padre=raiz, nombre="Hija")
        response = self.client.post(
            self._url_org("carpeta-mover", hija_de_raiz.pk),
            {"padre_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_eliminar_desvincula_archivos(self):
        carpeta = self._crear_carpeta(nombre="Borrar")
        hija = self._crear_carpeta(padre=carpeta, nombre="Hija")
        archivo = self._crear_archivo(carpeta=carpeta)
        archivo_hijo = self._crear_archivo(carpeta=hija, clave_s3="clave-hijo")
        response = self.client.delete(self._url_org("carpeta-detail", carpeta.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        for obj in (carpeta, hija):
            self.assertFalse(Carpeta.objects.filter(pk=obj.pk).exists())
        archivo.refresh_from_db()
        archivo_hijo.refresh_from_db()
        self.assertIsNone(archivo.carpeta_id)
        self.assertIsNone(archivo_hijo.carpeta_id)
        self.assertFalse(archivo.en_papelera)
        response_list = self.client.get(self._url_org("carpeta-list"))
        self.assertEqual(response_list.data["data"]["count"], 0)

    def test_contenido_lista_hijos(self):
        carpeta = self._crear_carpeta(nombre="Caja")
        hija = self._crear_carpeta(padre=carpeta, nombre="Hija")
        archivo = self._crear_archivo(carpeta=carpeta, nombre="a.txt")
        response = self.client.get(self._url_org("carpeta-contenido", carpeta.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual({c["id"] for c in data["subcarpetas"]}, {str(hija.pk)})
        self.assertEqual({c["id"] for c in data["archivos"]}, {str(archivo.pk)})
