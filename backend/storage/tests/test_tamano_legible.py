from django.test import TestCase

from accounts.models import User
from storage.models import FileMetadata
from storage.serializers import FileMetadataSerializer


class TamanoLegibleTests(TestCase):
    def test_tamano_legible_usa_punto_decimal(self):
        user = User.objects.create_user(email="t@x.io", password="ClaveSegura123", full_name="T")
        archivo = FileMetadata.objects.create(
            owner=user, nombre_original="a.pdf", clave_s3="k1", tamano_bytes=4404019
        )
        self.assertEqual(FileMetadataSerializer(archivo).data["tamano_legible"], "4.2 MB")
