from datetime import datetime, timedelta, timezone
from uuid import UUID

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from auth_workspaces.serializers_administracion import (
    EstadoCuentaInputSerializer, UsuarioAdministrativoSerializer,
)


class EntradaEstadoCuentaTests(SimpleTestCase):
    def datos(self, **cambios):
        return {"esta_activo": False, "motivo": "Revisión administrativa", **cambios}

    def test_booleanos_exactos_y_motivo_recortado(self):
        for estado in (True, False):
            with self.subTest(estado=estado):
                serializer = EstadoCuentaInputSerializer(data=self.datos(
                    esta_activo=estado, motivo="  Revisión administrativa \n",
                ))
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data, {
                    "esta_activo": estado, "motivo": "Revisión administrativa",
                })

    def test_no_coacciona_numeros_strings_o_null_a_booleano(self):
        for valor in (0, 1, 0.0, 1.0, "true", "false", "0", "1", "sí", None, [], {}):
            with self.subTest(tipo=type(valor).__name__):
                serializer = EstadoCuentaInputSerializer(data=self.datos(esta_activo=valor))
                self.assertFalse(serializer.is_valid())
                self.assertIn("esta_activo", serializer.errors)

    def test_motivo_1_y_500_despues_de_recortar(self):
        for largo in (1, 500):
            with self.subTest(largo=largo):
                serializer = EstadoCuentaInputSerializer(data=self.datos(motivo="  " + "á" * largo + "  "))
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(len(serializer.validated_data["motivo"]), largo)

    def test_motivo_vacio_blanco_o_501_es_rechazado(self):
        for valor in ("", " ", "\n\t", "\u00a0", "a" * 501):
            with self.subTest(largo=len(valor)):
                serializer = EstadoCuentaInputSerializer(data=self.datos(motivo=valor))
                self.assertFalse(serializer.is_valid())
                self.assertIn("motivo", serializer.errors)

    def test_motivo_no_string_no_se_coacciona(self):
        for valor in (None, 1, 1.5, True, [], {}):
            with self.subTest(tipo=type(valor).__name__):
                serializer = EstadoCuentaInputSerializer(data=self.datos(motivo=valor))
                self.assertFalse(serializer.is_valid())
                self.assertIn("motivo", serializer.errors)

    def test_ambos_campos_son_obligatorios(self):
        for ausente in ("esta_activo", "motivo"):
            datos = self.datos()
            del datos[ausente]
            with self.subTest(campo=ausente):
                serializer = EstadoCuentaInputSerializer(data=datos)
                self.assertFalse(serializer.is_valid())
                self.assertIn(ausente, serializer.errors)

    def test_patch_parcial_no_permite_omitir_campos_del_contrato(self):
        for datos in ({}, {"esta_activo": False}, {"motivo": "Revisión"}):
            with self.subTest(campos=sorted(datos)):
                serializer = EstadoCuentaInputSerializer(data=datos, partial=True)
                self.assertFalse(serializer.is_valid())
                self.assertTrue((set(self.datos()) - set(datos)) <= set(serializer.errors))
        completo = EstadoCuentaInputSerializer(data=self.datos(), partial=True)
        self.assertTrue(completo.is_valid(), completo.errors)

    def test_rechaza_campos_adicionales_y_privilegios(self):
        for nombre, valor in (
            ("id", "synthetic-id"), ("is_superuser", True), ("es_superusuario", True),
            ("nivel_rol", 0), ("rol", "PROPIETARIO"), ("password", "synthetic-private-value"),
            ("organizacion_id", "synthetic-id"),
        ):
            with self.subTest(campo=nombre):
                serializer = EstadoCuentaInputSerializer(data={**self.datos(), nombre: valor})
                self.assertFalse(serializer.is_valid())
                self.assertIn(nombre, serializer.errors)
                self.assertNotIn("synthetic-private-value", str(serializer.errors))

    def test_rechaza_estructuras_alternativas_y_claves_no_json(self):
        for datos in (None, [], [self.datos()], "synthetic", True, 1, {**self.datos(), 1: "extra"}):
            with self.subTest(tipo=type(datos).__name__):
                serializer = EstadoCuentaInputSerializer(data=datos)
                self.assertFalse(serializer.is_valid())

    def test_motivo_no_forma_parte_de_la_representacion(self):
        serializer = EstadoCuentaInputSerializer(data=self.datos(motivo="synthetic-private-value"))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.data, {"esta_activo": False})

    def test_validar_no_guarda_ni_ofrece_mutacion_operativa(self):
        serializer = EstadoCuentaInputSerializer(data=self.datos())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(NotImplementedError):
            serializer.save()


class ProyeccionUsuarioAdministrativoTests(SimpleTestCase):
    def fila(self, **cambios):
        return {
            "id": UUID("a0000000-0000-4000-8000-000000000001"),
            "nombre_completo": "Cuenta de prueba",
            "correo_electronico": "offline@example.test",
            "esta_activo": True,
            "organizaciones_count": 2,
            "almacenamiento_propietario_bytes": 987654321012345,
            "fecha_registro": datetime(2026, 10, 31, 12, tzinfo=timezone.utc),
            **cambios,
        }

    def test_campos_exactos_uuid_y_bytes_sin_perdida(self):
        self.assertEqual(UsuarioAdministrativoSerializer(self.fila()).data, {
            "id": "a0000000-0000-4000-8000-000000000001",
            "nombre_completo": "Cuenta de prueba",
            "correo_electronico": "offline@example.test",
            "esta_activo": True,
            "organizaciones_count": 2,
            "almacenamiento_propietario_bytes": 987654321012345,
            "fecha_registro": "2026-10-31T12:00:00Z",
        })

    def test_descarta_secretos_plan_individual_y_privilegio_no_soportado(self):
        fila = self.fila(**{
            nombre: "synthetic-private-value" for nombre in (
                "password", "contrasena_hash", "palabra_secreta_hash", "totp_secret",
                "access", "refresh", "clave_s3", "ip_origen", "is_superuser",
                "es_superusuario", "plan_actual",
            )
        })
        salida = UsuarioAdministrativoSerializer(fila).data
        self.assertEqual(set(salida), set(self.fila()))
        self.assertNotIn("synthetic-private-value", str(salida))

    def test_cero_es_valido_solo_si_los_totales_son_explicitos(self):
        salida = UsuarioAdministrativoSerializer(self.fila(
            organizaciones_count=0, almacenamiento_propietario_bytes=0,
        )).data
        self.assertEqual(salida["organizaciones_count"], 0)
        self.assertEqual(salida["almacenamiento_propietario_bytes"], 0)

    def test_no_omite_campos_ni_inventa_totales_ausentes(self):
        for campo in self.fila():
            fila = self.fila()
            del fila[campo]
            with self.subTest(campo=campo), self.assertRaises(ValidationError) as error:
                UsuarioAdministrativoSerializer(fila).data
            self.assertIn(campo, error.exception.detail)

    def test_agregados_invalidos_no_se_coaccionan_a_cero_o_enteros(self):
        for campo in ("organizaciones_count", "almacenamiento_propietario_bytes"):
            for valor in (-1, None, True, False, "2", 1.5):
                with self.subTest(campo=campo, tipo=type(valor).__name__), self.assertRaises(ValidationError):
                    UsuarioAdministrativoSerializer(self.fila(**{campo: valor})).data

    def test_fecha_se_normaliza_a_utc(self):
        fecha = datetime(2026, 10, 31, 14, tzinfo=timezone(timedelta(hours=2)))
        salida = UsuarioAdministrativoSerializer(self.fila(fecha_registro=fecha)).data
        self.assertEqual(salida["fecha_registro"], "2026-10-31T12:00:00Z")

    def test_fecha_inconsistente_no_se_fabrica(self):
        for valor in (None, "2026-10-31", datetime(2026, 10, 31, 12)):
            with self.subTest(tipo=type(valor).__name__), self.assertRaises(ValidationError):
                UsuarioAdministrativoSerializer(self.fila(fecha_registro=valor)).data

    def test_estado_y_datos_publicos_no_se_coaccionan(self):
        for campo, valor in (("esta_activo", "true"), ("esta_activo", 1), ("nombre_completo", 1), ("correo_electronico", True)):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                UsuarioAdministrativoSerializer(self.fila(**{campo: valor})).data

    def test_uuid_y_correo_invalidos_no_generan_fila_parcial(self):
        for campo, valor in (("id", "no-es-uuid"), ("id", 1), ("id", True), ("correo_electronico", "correo-invalido")):
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                UsuarioAdministrativoSerializer(self.fila(**{campo: valor})).data

    def test_representacion_rechaza_estructura_incompleta(self):
        for fila in (None, [], "synthetic", object()):
            with self.subTest(tipo=type(fila).__name__), self.assertRaises(ValidationError):
                UsuarioAdministrativoSerializer(fila).data

    def test_proyeccion_no_modifica_el_nombre_almacenado(self):
        salida = UsuarioAdministrativoSerializer(self.fila(nombre_completo=" Cuenta ")).data
        self.assertEqual(salida["nombre_completo"], " Cuenta ")

    def test_lista_serializada_no_agrega_defaults_a_filas_incompletas(self):
        fila_incompleta = self.fila()
        del fila_incompleta["organizaciones_count"]
        with self.assertRaises(ValidationError):
            UsuarioAdministrativoSerializer([self.fila(), fila_incompleta], many=True).data

    def test_datos_validados_pueden_proyectarse_sin_guardar(self):
        serializer = UsuarioAdministrativoSerializer(data=self.fila())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(NotImplementedError):
            serializer.save()
        self.assertEqual(serializer.data["organizaciones_count"], 2)

    def test_validacion_de_fila_tampoco_coacciona_los_agregados(self):
        for campo in ("organizaciones_count", "almacenamiento_propietario_bytes"):
            for valor in ("2", True, None, -1):
                with self.subTest(campo=campo, tipo=type(valor).__name__):
                    serializer = UsuarioAdministrativoSerializer(data=self.fila(**{campo: valor}))
                    self.assertFalse(serializer.is_valid())
                    self.assertIn(campo, serializer.errors)
