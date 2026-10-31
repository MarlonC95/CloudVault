from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.test import APIClient
from auth_workspaces.views_organizaciones import MiembrosOrganizacionView
from auth_workspaces.views_auditoria import AuditoriaOrganizacionView

class RutasAdministracionTests(SimpleTestCase):
    def test_rutas_productivas_conectan_las_vistas_autorizadas(self):
        for sufijo, vista in (("miembros", MiembrosOrganizacionView), ("auditoria", AuditoriaOrganizacionView)):
            ruta = f"/api/v1/organizaciones/00000000-0000-4000-8000-000000000001/{sufijo}/"
            self.assertIs(resolve(ruta).func.view_class, vista)
            respuesta = APIClient().get(ruta)
            self.assertEqual(respuesta.status_code, 401)
            self.assertEqual(respuesta.data["error"]["code"], "NO_AUTENTICADO")
