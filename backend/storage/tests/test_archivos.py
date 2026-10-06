import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from storage.models import FileMetadata, Folder
from storage.services import get_used_bytes

User = get_user_model()


class ArchivoAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="user@example.com",
            password="password123",
            full_name="Usuario A",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="password123",
            full_name="Usuario B",
        )
        self.token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token.access_token}")

    def _file(self, owner=None, **kwargs):
        owner = owner or self.user
        defaults = {
            "clave_s3": f"key-{uuid.uuid4()}",
            "nombre_original": "file.txt",
            "tamano_bytes": 1024,
        }
        defaults.update(kwargs)
        return FileMetadata.objects.create(owner=owner, **defaults)

    def _folder(self, owner=None, **kwargs):
        owner = owner or self.user
        return Folder.objects.create(owner=owner, **kwargs)

    # Auth

    def test_list_requires_auth(self):
        self.client.credentials()
        response = self.client.get(reverse("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detail_requires_auth(self):
        archivo = self._file()
        self.client.credentials()
        response = self.client.get(reverse("archivo-detail", args=[archivo.pk]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_requires_auth(self):
        archivo = self._file()
        self.client.credentials()
        response = self.client.patch(
            reverse("archivo-detail", args=[archivo.pk]),
            {"nombre": "nuevo.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_move_requires_auth(self):
        archivo = self._file()
        self.client.credentials()
        response = self.client.post(
            reverse("archivo-mover", args=[archivo.pk]),
            {"carpeta_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # Isolation

    def test_isolation_list(self):
        self._file(owner=self.user, nombre_original="mio.txt")
        self._file(owner=self.other, nombre_original="otro.txt")
        response = self.client.get(reverse("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"mio.txt"})

    def test_isolation_detail_returns_404(self):
        ajeno = self._file(owner=self.other, nombre_original="ajeno.txt")
        response = self.client.get(reverse("archivo-detail", args=[ajeno.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "NO_ENCONTRADO")

    def test_isolation_patch_returns_404(self):
        ajeno = self._file(owner=self.other, nombre_original="ajeno.txt")
        response = self.client.patch(
            reverse("archivo-detail", args=[ajeno.pk]),
            {"nombre": "hackeado.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_isolation_move_returns_404(self):
        ajeno = self._file(owner=self.other, nombre_original="ajeno.txt")
        carpeta = self._folder(nombre="Destino")
        response = self.client.post(
            reverse("archivo-mover", args=[ajeno.pk]),
            {"carpeta_id": str(carpeta.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Trash exclusion

    def test_list_excludes_trash(self):
        self._file(nombre_original="activo.txt")
        self._file(nombre_original="basura.txt", en_papelera=True)
        response = self.client.get(reverse("archivo-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"activo.txt"})

    # Filters

    def test_filter_by_carpeta(self):
        carpeta = self._folder(nombre="Docs")
        self._file(nombre_original="raiz.txt", carpeta=None)
        self._file(nombre_original="en_docs.txt", carpeta=carpeta)

        response = self.client.get(reverse("archivo-list") + "?carpeta=null")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"raiz.txt"})

        response = self.client.get(reverse("archivo-list") + f"?carpeta={carpeta.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"en_docs.txt"})

    def test_filter_by_busqueda(self):
        self._file(nombre_original="contrato.pdf")
        self._file(nombre_original="foto.png")
        response = self.client.get(reverse("archivo-list") + "?busqueda=cont")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"contrato.pdf"})

    def test_filter_by_tipo(self):
        self._file(nombre_original="doc.pdf")
        self._file(nombre_original="sheet.xlsx")
        self._file(nombre_original="script.js")
        self._file(nombre_original="readme")

        response = self.client.get(reverse("archivo-list") + "?tipo=pdf")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"doc.pdf"})

        response = self.client.get(reverse("archivo-list") + "?tipo=otro")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {a["nombre"] for a in response.data["data"]["results"]}
        self.assertEqual(nombres, {"readme"})

    # Rename

    def test_rename(self):
        archivo = self._file(nombre_original="viejo.txt")
        response = self.client.patch(
            reverse("archivo-detail", args=[archivo.pk]),
            {"nombre": "nuevo.txt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["nombre"], "nuevo.txt")
        archivo.refresh_from_db()
        self.assertEqual(archivo.nombre_original, "nuevo.txt")

    # Move

    def test_move_to_folder(self):
        archivo = self._file(nombre_original="mover.txt")
        carpeta = self._folder(nombre="Destino")
        response = self.client.post(
            reverse("archivo-mover", args=[archivo.pk]),
            {"carpeta_id": str(carpeta.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["carpeta_id"], str(carpeta.pk))
        archivo.refresh_from_db()
        self.assertEqual(archivo.carpeta_id, carpeta.pk)

    def test_move_to_root(self):
        carpeta = self._folder(nombre="Origen")
        archivo = self._file(nombre_original="raiz.txt", carpeta=carpeta)
        response = self.client.post(
            reverse("archivo-mover", args=[archivo.pk]),
            {"carpeta_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["data"]["carpeta_id"])
        archivo.refresh_from_db()
        self.assertIsNone(archivo.carpeta_id)

    # Validation

    def test_rename_empty_name(self):
        archivo = self._file(nombre_original="x.txt")
        response = self.client.patch(
            reverse("archivo-detail", args=[archivo.pk]),
            {"nombre": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_move_rejects_missing_folder(self):
        archivo = self._file(nombre_original="x.txt")
        response = self.client.post(
            reverse("archivo-mover", args=[archivo.pk]),
            {"carpeta_id": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("carpeta_id", response.data["error"]["fields"])

    def test_move_rejects_other_user_folder(self):
        archivo = self._file(nombre_original="x.txt")
        ajena = self._folder(owner=self.other, nombre="Ajena")
        response = self.client.post(
            reverse("archivo-mover", args=[archivo.pk]),
            {"carpeta_id": str(ajena.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("carpeta_id", response.data["error"]["fields"])


class ArchivoServiceTests(APITestCase):
    def test_get_used_bytes_sums_active_files(self):
        user = User.objects.create_user(
            email="owner@example.com",
            password="password123",
            full_name="Owner",
        )
        other = User.objects.create_user(
            email="otro@example.com",
            password="password123",
            full_name="Otro",
        )
        FileMetadata.objects.create(
            owner=user,
            clave_s3="key-1",
            nombre_original="a.txt",
            tamano_bytes=100,
        )
        FileMetadata.objects.create(
            owner=user,
            clave_s3="key-2",
            nombre_original="b.txt",
            tamano_bytes=250,
        )
        FileMetadata.objects.create(
            owner=other,
            clave_s3="key-3",
            nombre_original="c.txt",
            tamano_bytes=999,
        )

        self.assertEqual(get_used_bytes(user), 350)
