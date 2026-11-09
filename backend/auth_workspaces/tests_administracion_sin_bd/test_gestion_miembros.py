from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.test import APIClient
from auth_workspaces.gestion_miembros import ServicioMiembros, RepositorioMiembros, PropietarioProtegido

A=UUID("10000000-0000-4000-8000-000000000001")
U=UUID("20000000-0000-4000-8000-000000000001")
O=UUID("30000000-0000-4000-8000-000000000001")

class Repo:
    def __init__(self):
        self.miembro=SimpleNamespace(usuario_id=U,nivel_rol=2)
        self.eventos=[];self.acl={"org":True,"otra":True};self.archivos=["conservado"]
        self.permitido=True;self.falla=False
    @contextmanager
    def transaccion(self, org):
        estado=deepcopy((self.miembro,self.eventos,self.acl))
        try: yield
        except Exception:
            self.miembro,self.eventos,self.acl=estado
            raise
    def autorizar(self, actor, org):
        if not self.permitido or org != O: raise PermissionDenied()
    def objetivo(self,*args): return self.miembro
    def cambiar(self,m,n): m.nivel_rol=n
    def retirar(self,m,org): self.acl.pop("org");self.miembro=None
    def auditar(self,*args):
        if self.falla: raise RuntimeError("auditoría fallida")
        self.eventos.append(args)

class GestionMiembrosTests(SimpleTestCase):
    def setUp(self): self.repo=Repo();self.servicio=ServicioMiembros(self.repo)
    def test_cambio_enum_y_repeticion_sin_evento_duplicado(self):
        self.assertTrue(self.servicio.ejecutar(A,O,U,rol="LECTOR_NV1"))
        self.assertEqual(self.repo.miembro.nivel_rol,1)
        self.assertFalse(self.servicio.ejecutar(A,O,U,rol="LECTOR_NV1"))
        self.assertEqual(len(self.repo.eventos),1)
    def test_enum_invalido_no_modifica(self):
        for rol in [None,0,True,"1","propietario",{},[]]:
            with self.subTest(rol=rol),self.assertRaises(ValidationError):self.servicio.ejecutar(A,O,U,rol=rol)
        self.assertEqual(self.repo.miembro.nivel_rol,2)
    def test_owner_inmutable(self):
        self.repo.miembro.nivel_rol=0
        for retirar in [False,True]:
            with self.assertRaises(PropietarioProtegido):self.servicio.ejecutar(A,O,U,rol="AVANZADO_NV3",retirar=retirar)
        self.assertFalse(self.repo.eventos)
    def test_sin_permiso_no_muta(self):
        self.repo.permitido=False
        with self.assertRaises(PermissionDenied):self.servicio.ejecutar(A,O,U,retirar=True)
        self.assertIsNotNone(self.repo.miembro)
    def test_retirar_preserva_archivos_y_otra_acl_repeticion_idempotente(self):
        self.assertTrue(self.servicio.ejecutar(A,O,U,retirar=True))
        self.assertEqual(self.repo.acl,{"otra":True});self.assertEqual(self.repo.archivos,["conservado"])
        self.assertFalse(self.servicio.ejecutar(A,O,U,retirar=True));self.assertEqual(len(self.repo.eventos),1)
    def test_fallo_auditoria_revierte_cambio_y_retirada_en_doble(self):
        self.repo.falla=True
        for retirar in [False,True]:
            with self.assertRaises(RuntimeError):self.servicio.ejecutar(A,O,U,rol="LECTOR_NV1",retirar=retirar)
            self.assertEqual(self.repo.miembro.nivel_rol,2);self.assertIn("org",self.repo.acl)
    def test_cambio_ausente_404(self):
        self.repo.miembro=None
        with self.assertRaises(NotFound):self.servicio.ejecutar(A,O,U,rol="LECTOR_NV1")
    def test_acl_sql_parametrizado_acotado_y_solo_borra_membresia(self):
        miembro=MagicMock(usuario_id=U)
        with patch("auth_workspaces.gestion_miembros.connections") as conexiones:
            cursor=conexiones.__getitem__.return_value.cursor.return_value.__enter__.return_value
            RepositorioMiembros().retirar(miembro,O)
            sql,parametros=cursor.execute.call_args.args
            self.assertEqual(parametros,[U,O,O]);self.assertIn("a.organizacion_id=%s",sql);self.assertIn("c.organizacion_id=%s",sql)
            self.assertNotIn("DELETE FROM archivos",sql);miembro.delete.assert_called_once()
    def test_http_payload_y_scope_sin_llegar_servicio(self):
        cliente=APIClient();cliente.force_authenticate(SimpleNamespace(pk=A,is_authenticated=True))
        ruta=f"/api/v1/organizaciones/{O}/miembros/{U}/"
        with patch("auth_workspaces.gestion_miembros.ServicioMiembros.ejecutar") as ejecutar:
            for datos in [[],{"rol":"LECTOR_NV1","extra":1}]:
                self.assertEqual(cliente.patch(ruta,datos,format="json").status_code,400)
            self.assertEqual(cliente.delete(ruta,{"rol":"LECTOR_NV1"},format="json").status_code,400)
            ejecutar.assert_not_called()
    def test_http_exito_espera_servicio_y_owner_conflicto(self):
        cliente=APIClient();cliente.force_authenticate(SimpleNamespace(pk=A,is_authenticated=True))
        ruta=f"/api/v1/organizaciones/{O}/miembros/{U}/"
        with patch("auth_workspaces.gestion_miembros.ServicioMiembros.ejecutar") as ejecutar:
            self.assertEqual(cliente.patch(ruta,{"rol":"LECTOR_NV1"},format="json").status_code,200)
            ejecutar.side_effect=PropietarioProtegido()
            respuesta=cliente.delete(ruta)
            self.assertEqual(respuesta.status_code,409);self.assertEqual(respuesta.data["error"]["code"],"OWNER_REQUIRED")

    def test_repositorio_revalida_owner_unico_cuenta_y_membresia(self):
        with patch("auth_workspaces.gestion_miembros.Usuario.objects") as usuarios, patch("auth_workspaces.gestion_miembros.MiembroOrganizacion.objects") as miembros:
            usuarios.select_for_update.return_value.filter.return_value.first.return_value=SimpleNamespace(pk=A)
            consulta=miembros.select_for_update.return_value.filter
            consulta.return_value.first.return_value=SimpleNamespace(nivel_rol=0)
            consulta.return_value.values_list.return_value=[A]
            repo=RepositorioMiembros()
            repo.autorizar(A,O)
            consulta.return_value.values_list.return_value=[A,U]
            with self.assertRaises(PermissionDenied):repo.autorizar(A,O)
            consulta.return_value.values_list.return_value=[A]
            for nivel in [1,2,3,True,99]:
                consulta.return_value.first.return_value=SimpleNamespace(nivel_rol=nivel)
                with self.assertRaises(PermissionDenied):repo.autorizar(A,O)
            consulta.return_value.first.return_value=None
            with self.assertRaises(NotFound):repo.autorizar(A,O)
            usuarios.select_for_update.return_value.filter.return_value.first.return_value=None
            with self.assertRaises(PermissionDenied):repo.autorizar(A,O)

    def test_asignacion_propietario_es_conflicto(self):
        with self.assertRaises(PropietarioProtegido):self.servicio.ejecutar(A,O,U,rol="PROPIETARIO")

    def test_http_rechaza_actor_sin_membresia_y_roles_bajos_con_repo_real(self):
        from contextlib import nullcontext
        cliente=APIClient();cliente.force_authenticate(SimpleNamespace(pk=A,is_authenticated=True))
        ruta=f"/api/v1/organizaciones/{O}/miembros/{U}/"
        with patch.object(RepositorioMiembros,"transaccion",return_value=nullcontext()), patch("auth_workspaces.gestion_miembros.Usuario.objects") as usuarios, patch("auth_workspaces.gestion_miembros.MiembroOrganizacion.objects") as miembros:
            usuarios.select_for_update.return_value.filter.return_value.first.return_value=SimpleNamespace(pk=A)
            consulta=miembros.select_for_update.return_value.filter
            consulta.return_value.values_list.return_value=[U]
            consulta.return_value.first.return_value=None
            self.assertEqual(cliente.delete(ruta).status_code,404)
            for nivel in [1,2,3]:
                consulta.return_value.first.return_value=SimpleNamespace(nivel_rol=nivel)
                self.assertEqual(cliente.patch(ruta,{"rol":"LECTOR_NV1"},format="json").status_code,403)
            usuarios.select_for_update.return_value.filter.assert_called_with(pk=A,is_active=True,is_2fa_enabled=False)

    def test_proyeccion_auditoria_muestra_solo_identidad_y_roles_tipados(self):
        from auth_workspaces.contratos_auditoria import detalles_publicos
        datos={"usuario_afectado_id":str(U),"nivel_anterior":2,"nivel_nuevo":1,"secreto":"omitido"}
        self.assertEqual(detalles_publicos("MEMBER_ROLE_CHANGED",datos),{k:v for k,v in datos.items() if k!="secreto"})
