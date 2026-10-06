# Almacenamiento de Dani — fases 01, 02 y cliente de fase 03

Estado: **contrato y persistencia técnica implementados y probados localmente**. El cliente S3 de fase 03 está implementado y probado localmente; la validación Railway sigue pendiente porque el acceso con `.env` devolvió `403 InvalidAccessKeyId`. Proveedores reales de negocio/SQL y endpoints siguen pendientes.

## Componentes disponibles

| Archivo | Función |
|---|---|
| `contrato.py` | Rutas/status del PDF, catálogo de errores, límites SQL y política operativa configurable |
| `serializers.py` | Validación estricta de inicio/confirmación/ID y estructuras de respuesta |
| `errores.py` | Traducción local de errores al catálogo del PDF, con respuesta segura |
| `integracion.py` | Tipos y protocolos para consumir destino, cuota y archivos de los módulos compartidos |
| `openapi.py` | Exporta el contrato de diseño sin registrar vistas ficticias |
| `models.py` | Mapping `managed=False` completo de las dos tablas técnicas del esquema vigente |
| `persistencia.py` | Unidades de trabajo, sesiones, pendientes, ledger, transiciones y callback de confirmación atómico |
| `adaptadores.py` | Valida la frontera con proveedores reales de destino/cuota/metadatos/descarga |
| `validacion.py` | Validadores públicos internos de texto técnico y checksum, compartidos por persistencia y adaptadores |
| `esquema.py` | Inspección de solo lectura de mapping, constraints, índice y triggers |
| `tests/` | Casos positivos, negativos, límites, OpenAPI y seguridad; configuración sin base de datos |
| `tests_persistencia/` | PostgreSQL desechable, SQL literal y pruebas de persistencia/concurrencia/rollback/recuperación |

No hay migraciones ni rutas de archivos ejecutables. El cliente S3 es una primitiva interna: no autoriza ni reserva cuota por sí mismo. Las interfaces/adaptadores no implementan modelos, CRUD, planes ni permisos de otros integrantes. La autenticación y su handler global conservan su código. El único cambio compartido es registrar la app propia en `config/settings.py`; no instala SQL al arrancar.

## Probar

Desde `backend/`, usando el entorno con las dependencias de `requirements.txt` instaladas:

```bash
.venv/bin/python -m django test almacenamiento.tests auth_workspaces.tests.test_error_security --settings=almacenamiento.tests.settings --verbosity=2
```

En Windows o con otro entorno, sustituir `.venv/bin/python` por su ejecutable Python. La configuración indicada no lee `.env`, usa `DATABASES={}` y no instala SQL ni consulta storage. No ejecutar la suite de contrato con `config.settings` o el runner de base compartida.

## Probar persistencia con PostgreSQL real aislado

Desde `backend/`, con `initdb` y `pg_ctl` locales de la misma instalación:

```bash
.venv/bin/python -m almacenamiento.tests_persistencia.ejecutar
```

Arranca un clúster nuevo sin TCP en `/private/tmp`, instala la copia SQL literal con prerrequisitos exclusivos de prueba y ejecuta persistencia, adaptadores, contrato y seguridad. Verifica la identidad del servidor antes de los tests y lo detiene/elimina al finalizar. No usa `.env` ni la DB de aplicación. No lanzar `tests_persistencia` con otro runner/configuración. Tras las mejoras de seguridad, el resultado local es **89 pruebas aprobadas con PostgreSQL 17.11**; consultar [resultado y evidencia](../../auditoria/resultado-seguridad-fases01-02.md). Las [83 pruebas anteriores](../../auditoria/resultado-mejoras-fases01-02.md) conservan su registro histórico.

Los límites SQL de clave temporal y ledger conservan 1024 caracteres; la clave final publicable conserva 255 para caber en `archivos.clave_s3`. Las constantes distinguen estas restricciones. Los validadores compartidos no cambian las reglas del JSON público. `context` se conserva en el handler para aceptar los dos argumentos que pasa DRF; su conexión se probó en una vista exclusiva de test, sin registrar endpoints de almacenamiento.

## Diagnóstico compartido de solo lectura

Con el entorno SQL de aplicación configurado y autorización de lectura:

```bash
.venv/bin/python manage.py inspeccionar_almacenamiento
```

Devuelve un informe de compatibilidad técnica y advertencias. No instala ni repara SQL. No se ejecutó contra Railway en esta intervención. `managed=False` requiere instalación previa del esquema por Marlon; Django no la realiza.

## Exportar el contrato de diseño

Desde `backend/`:

```bash
.venv/bin/python -m almacenamiento.openapi --output ../agente/contrato-fase-01.openapi.json
```

El archivo exportado está marcado como diseño. El Swagger de `/api/docs/` sigue describiendo únicamente las vistas reales instaladas; las pruebas comprueban que no anuncie estas operaciones como disponibles.

## Uso posterior

```python
from almacenamiento.contrato import PoliticaCarga
from almacenamiento.serializers import IniciarCargaInputSerializer

entrada = IniciarCargaInputSerializer(
    data=body,
    context={"politica": PoliticaCarga(maximo_archivo_bytes=1073741824)},
)
entrada.is_valid(raise_exception=True)
```

Una entrada estructuralmente válida aún requiere autorización, cuota y reserva antes de firmar. Las vistas de Dani podrán usar `errores.error_de_almacenamiento` como handler local; no configurarlo globalmente para cambiar los endpoints ajenos.

El adaptador exige UUID de actor/archivo antes de consultar la autorización de descarga y propaga denegaciones actuales del proveedor. Es una validación de frontera: German sigue siendo la autoridad de permisos. Las pruebas de aislamiento cubren las primitivas internas y los errores de autenticación se ejercitan con una vista y un autenticador sintéticos; no acreditan JWT real ni endpoints instalados.

`expira_en` vence la sesión, no elimina el objeto S3. La limpieza real pertenece a fase 07. La confirmación repetida es idempotente; el inicio HTTP no promete deduplicación. El SQL recibido concede lectura al rol compartido y no se modificó; su política pertenece a Marlon. Antes de integrar el bucket se requieren secretos vigentes gestionados fuera del código, sin reutilizar automáticamente credenciales versionadas.

El generador OpenAPI admite `crear_openapi(politica=...)` para documentar un perfil operativo distinto. Al cambiar el límite en una futura configuración, exportar el mismo perfil que se utiliza en las vistas y volver a comprobar la correspondencia.

Leer [decisiones de contrato](../../agente/contrato-fase-01.md), [persistencia e integración](../../agente/persistencia-fase-02.md), [evidencia de fase 02](../../agente/evidencia-fase-02.md) e [inventario funcional](../../agente/funcionalidades-fases-01-y-02.md). La documentación de [DRF](https://www.django-rest-framework.org/api-guide/serializers/) y [drf-spectacular](https://drf-spectacular.readthedocs.io/en/stable/readme.html) explica las herramientas reutilizadas.

## Cliente S3 — fase 03

`configuracion_s3.py` selecciona perfiles independientes; `s3.py` firma PUT/GET, consulta, verifica hash real por bloques, copia condicionalmente y borra claves técnicas propias. `probar_s3.py` hace un ensayo opt-in con objetos nuevos y limpieza; `ensayo_s3.html` prueba CORS desde un navegador sin modificar React. `infra/` contiene el contenedor de pruebas propio, con contexto limitado mediante `Dockerfile.dockerignore`.

Ver [configuración y reproducción](../../agente/cliente-s3-fase-03.md) y [evidencia y límites](../../agente/evidencia-fase-03.md). Se mantienen sin cambios los campos públicos del PDF, la autenticación, los modelos/CRUD/planes ajenos y el SQL compartido. El único cambio compartido de esta fase es incorporar boto3 en `requirements.txt`.
