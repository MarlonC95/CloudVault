from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from storage.models import FileMetadata, Folder

User = get_user_model()


class StorageFolderTests(APITestCase):
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

    def _folder(self, owner=None, **kwargs):
        owner = owner or self.user
        return Folder.objects.create(owner=owner, **kwargs)

    def _file(self, owner=None, **kwargs):
        owner = owner or self.user
        defaults = {"clave_s3": f"key-{owner.email}-{Folder.objects.count()}", "nombre_original": "file.txt"}
        defaults.update(kwargs)
        return FileMetadata.objects.create(owner=owner, **defaults)

    def test_list_requires_auth(self):
        self.client.credentials()
        response = self.client.get(reverse("carpeta-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_requires_auth(self):
        self.client.credentials()
        response = self.client.post(reverse("carpeta-list"), {"nombre": "Docs"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_isolation_list(self):
        self._folder(owner=self.user, nombre="Mios")
        self._folder(owner=self.other, nombre="Otros")
        response = self.client.get(reverse("carpeta-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {c["nombre"] for c in response.data["data"]["results"]}
        self.assertEqual(nombres, {"Mios"})

    def test_isolation_detail_returns_404(self):
        ajena = self._folder(owner=self.other, nombre="Ajena")
        response = self.client.get(reverse("carpeta-detail", args=[ajena.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_name_returns_409(self):
        self._folder(nombre="Docs")
        response = self.client.post(reverse("carpeta-list"), {"nombre": "Docs"})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("nombre", response.data["error"]["fields"])

    def test_validation_empty_name(self):
        response = self.client.post(reverse("carpeta-list"), {"nombre": "  "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_create_computes_path_and_parent_id(self):
        response = self.client.post(reverse("carpeta-list"), {"nombre": "Documentos"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["ruta_completa"], "/Documentos")
        self.assertIsNone(response.data["data"]["padre_id"])

    def test_filter_by_padre(self):
        raiz = self._folder(nombre="Raiz")
        self._folder(padre=raiz, nombre="Hija")
        response = self.client.get(reverse("carpeta-list") + "?padre=null")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nombres = {c["nombre"] for c in response.data["data"]["results"]}
        self.assertEqual(nombres, {"Raiz"})

    def test_move_to_root_updates_paths(self):
        raiz = self._folder(nombre="Raiz")
        hija = self._folder(padre=raiz, nombre="Hija")
        nieto = self._folder(padre=hija, nombre="Nieto")
        response = self.client.post(reverse("carpeta-mover", args=[hija.pk]), {"padre_id": None}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        hija.refresh_from_db()
        nieto.refresh_from_db()
        self.assertIsNone(hija.padre_id)
        self.assertEqual(hija.ruta_completa, "/Hija")
        self.assertEqual(nieto.ruta_completa, "/Hija/Nieto")

    def test_move_rejects_cycle(self):
        raiz = self._folder(nombre="Raiz")
        hija = self._folder(padre=raiz, nombre="Hija")
        nieto = self._folder(padre=hija, nombre="Nieto")
        response = self.client.post(reverse("carpeta-mover", args=[raiz.pk]), {"padre_id": str(nieto.pk)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_move_rejects_self(self):
        carpeta = self._folder(nombre="Sola")
        response = self.client.post(reverse("carpeta-mover", args=[carpeta.pk]), {"padre_id": str(carpeta.pk)})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_leaves_files_null_and_removes_subfolders(self):
        carpeta = self._folder(nombre="Borrar")
        hija = self._folder(padre=carpeta, nombre="Hija")
        archivo = self._file(carpeta=carpeta)
        response = self.client.delete(reverse("carpeta-detail", args=[carpeta.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        archivo.refresh_from_db()
        self.assertIsNone(archivo.carpeta_id)
        self.assertFalse(Folder.objects.filter(pk=hija.pk).exists())

    def test_contenido_lists_children(self):
        carpeta = self._folder(nombre="Caja")
        hija = self._folder(padre=carpeta, nombre="Hija")
        archivo = self._file(carpeta=carpeta, nombre_original="a.txt")
        response = self.client.get(reverse("carpeta-contenido", args=[carpeta.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual({c["id"] for c in data["subcarpetas"]}, {str(hija.pk)})
        self.assertEqual({c["id"] for c in data["archivos"]}, {str(archivo.pk)})
