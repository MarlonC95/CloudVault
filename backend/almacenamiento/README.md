# Almacenamiento de Dani — fases 01 a 05

Estado al 6 de octubre de 2026: **componentes propios 01–05 implementados/probados**. Ensayo Railway/navegador aprobó PUT/GET/bytes/ETag y limpieza. Inicio/confirmación instalados con proveedor real, SQL compartido y mantenimiento pendientes. Descarga HTTP autorizada aún pendiente. La suite aislada aprobó 205 pruebas.

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
| `inicio.py`, `configuracion_inicio.py` | Reserva, cuota y firma antes de 201; configuración/fábrica real obligatoria |
| `confirmacion.py` | Reclamo, COPY único, verificación final y confirmación de metadatos externos antes de 200 |
| `verificacion.py`, `verificar_publicacion.py` | Hash final en proceso separado, con tamaño y timeout acotados |
| `views.py`, `urls.py`, `schema.py` | Inicio/confirmación HTTP, parser limitado, errores locales y Swagger JWT |
| `tests/` | Casos positivos, negativos, límites, OpenAPI y seguridad; configuración sin base de datos |
| `tests_persistencia/` | PostgreSQL desechable, SQL literal y pruebas de persistencia/concurrencia/rollback/recuperación |

No hay migraciones propias. Están instaladas inicio y confirmación; descarga todavía no tiene endpoint. El cliente S3 es una primitiva interna: no autoriza ni reserva cuota por sí mismo. Las interfaces/adaptadores no implementan modelos, CRUD, planes ni permisos de otros integrantes. La autenticación y su handler global conservan su código. Los cambios compartidos mínimos son el registro de app, boto3 y la inclusión del router propio; no instala SQL al arrancar.

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

Arranca un clúster nuevo sin TCP en `/private/tmp`, instala la copia SQL literal con prerrequisitos exclusivos de prueba y ejecuta persistencia, adaptadores, contrato y seguridad. Verifica la identidad del servidor antes de los tests y lo detiene/elimina al finalizar. No usa `.env` ni la DB de aplicación. No lanzar `tests_persistencia` con otro runner/configuración. El resultado vigente es **205 pruebas aprobadas con PostgreSQL 17.11**. El desglose vigente es 109 sin DB/red externa y 96 con PostgreSQL aislado.

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

El contrato exportado distingue inicio/confirmación implementados con integración pendiente de descarga todavía de diseño. Swagger real publica inicio, confirmación y auth; no anuncia descarga instalada.

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

Una entrada estructuralmente válida aún requiere autorización, cuota y reserva antes de firmar. La vista de Dani usa un handler local basado en `errores.error_de_almacenamiento`; no configurarlo globalmente para cambiar los endpoints ajenos.

El adaptador exige UUID de actor/archivo antes de consultar la autorización de descarga y propaga denegaciones actuales del proveedor. Es una validación de frontera: German sigue siendo la autoridad de permisos. La suite incluye el endpoint de inicio instalado y firma JWT válida con consulta de usuario sustituida; no acredita login ni permisos/plan reales del entorno compartido.

`expira_en` vence la sesión, no elimina el objeto S3. La limpieza real pertenece a fase 07. La confirmación repetida es idempotente; el inicio HTTP no promete deduplicación. El SQL recibido concede lectura al rol compartido y no se modificó; su política pertenece a Marlon. Antes de integrar el bucket se requieren secretos vigentes gestionados fuera del código, sin reutilizar automáticamente credenciales versionadas.

El generador OpenAPI admite `crear_openapi(politica=...)` para documentar un perfil operativo distinto. Al cambiar el límite en una futura configuración, exportar el mismo perfil que se utiliza en las vistas y volver a comprobar la correspondencia.

## Inicio de carga — fase 04

`POST /api/v1/archivos/iniciar-carga/` consume el JWT existente y devuelve HTTP 201 con UUID reservado, URL PUT, Content-Type y expiración. `inicio.py` coordina permiso, cuota organizacional, sesión PENDING, firma local y auditoría bajo transacción durable. No crea metadatos en archivos ni incrementa usado; los fallos revierten la reserva. `views.py` limita JSON a 16 KiB y protege las respuestas; `schema.py` conecta el esquema de autenticación en Swagger.

La variable/configuración `ALMACENAMIENTO_SERVICIOS_FACTORY` es obligatoria y debe apuntar a una fábrica real compatible con `integracion.py` y alias SQL default. Sin ella responde 503 antes de consultar tablas técnicas o firmar. No configurar proveedores sintéticos de tests. Política propia: `ALMACENAMIENTO_MAXIMO_ARCHIVO_BYTES`, `ALMACENAMIENTO_VIGENCIA_CARGA_SEGUNDOS`, `ALMACENAMIENTO_INICIOS_POR_VENTANA` y `ALMACENAMIENTO_VENTANA_INICIOS_SEGUNDOS`. Por defecto: máximo de archivo 1 GiB, carga 900 s, 10 inicios aceptados por usuario cada 60 s. Los valores deben ser enteros positivos; vigencia máxima 900 s.

La integración compartida aún requiere proveedor de permisos/plan/cuota, protocolo común de locks y SQL/auth compatibles. Las pruebas aisladas no certifican esa integración.

La especificación generada está en `agente/contrato-fase-01.openapi.json`. La referencia SQL literal que utiliza exclusivamente el runner aislado está en `agente/referencias/esquema-vigente.sql`; el runner no aplica ese esquema a la base compartida.

## Confirmación — fase 05

`POST /api/v1/archivos/{id}/confirmar-carga/` recibe body vacío/ETag opcional y devuelve 200 después de verificar final y confirmar metadatos por proveedor. PREPARED se confirma antes de COPY, con un intento SDK; un reintento solo verifica el destino. Si falta final, 503 para reconciliar, sin reemitir COPY. El final usa octet-stream/attachment; hash real en subprocess con lectura por bloques y timeout, fuera de transacciones de cuota.

El reclamo de publicador usa advisory lock de sesión PostgreSQL: requiere conexión directa/pool de sesiones, nunca pool de transacciones. Revalida destino/plan/cuota antes de SQL final y comprueba registro completo y consumo U→U+S. La autoridad de ese incremento es ajena; Dani no suma U. Ante falla de registro/auditoría/commit hay rollback y recuperación sin otra copia. La respuesta perdida se recupera con el mismo ID/resultado tras reautorizar, sin evento/uso duplicado.

Configuración adicional: `ALMACENAMIENTO_MAXIMO_PUBLICACION_BYTES` (por defecto menor de máximo operativo y 5 GiB, normalmente 1 GiB) y `ALMACENAMIENTO_VERIFICACION_SEGUNDOS` (60, máximo 300). El worker hereda entorno S3 cargado, no lee `.env` ni usa SQL. No configurar fixtures. No hay tareas de limpieza periódica ni borrado compensatorio del final: mantenimiento se reconstruye desde estados durables y continúa en fase 07.

Integración de negocio/SQL y nuevo COPY en Railway todavía no certificados. El hash acredita los bytes recibidos en el final; el contrato no incluye un checksum esperado del original. PREPARED sin final requiere reconciliación, sin repetir COPY. Cancelación pública y tareas periódicas de limpieza siguen pendientes.

## Cliente S3 — fase 03

`configuracion_s3.py` selecciona perfiles independientes; `s3.py` firma PUT/GET, consulta, verifica hash real por bloques, copia condicionalmente y borra claves técnicas propias. `probar_s3.py` hace un ensayo opt-in con objetos nuevos y limpieza; `ensayo_s3.html` prueba CORS desde un navegador sin modificar React. `infra/` contiene el contenedor de pruebas propio, con contexto limitado mediante `Dockerfile.dockerignore`.

Se mantienen sin cambios los campos públicos del PDF, la autenticación, los modelos/CRUD/planes ajenos y el SQL compartido. El único cambio compartido de esta fase es incorporar boto3 en `requirements.txt`.

## Configurar y comprobar CORS del ensayo

Desde `backend/`, consulta sin modificar el bucket:

```bash
.venv/bin/python -m almacenamiento.aplicar_cors
```

Para aplicar la política, únicamente con autorización sobre el bucket:

```bash
.venv/bin/python -m almacenamiento.aplicar_cors --aplicar
```

Usa el cliente S3 existente y carga explícitamente `backend/.env`, sin pedir ni imprimir secretos. Por defecto permite solo `http://127.0.0.1:8765`, PUT/GET, `content-type` y exposición de ETag. `--origen` es repetible para orígenes reales adicionales; sustituye la lista por defecto. Conserva reglas ajenas que el proveedor devuelva y guarda estado previo/propuesta en una carpeta temporal privada antes de escribir. Cuando hay reglas previas, incluye `cors-restaurable.json`. Si la lectura es no verificable o originalmente no existían reglas, no inventa un respaldo restaurable ni ejecuta DeleteBucketCors.

Una respuesta exitosa a PutBucketCors no acredita el arreglo: exige reglas devueltas y un OPTIONS que permita el origen exacto, PUT y content-type. No crea ni borra objetos. No habilitar debug SDK/HTTP.

Validación de transferencia con objetos sintéticos nuevos propios y limpieza:

```bash
.venv/bin/python -m almacenamiento.probar_s3 --ejecutar --perfil railway --navegador --duracion-navegador 240 --informe /private/tmp/cloudvault-cors-validacion.json
```

Abrir `http://127.0.0.1:8765` cuando el programa anuncie disponibilidad y pulsar el botón. Termina tras recibir el resultado o al vencer la ventana; las firmas no se almacenan en el informe. Con `--navegador`, el éxito exige preflight, PUT, GET, bytes exactos y ETag legible. Sin `--navegador`, solo certifica operaciones desde Python y muestra el preflight por separado. La herramienta no integra ni sustituye los endpoints de carga de Django ni el dashboard React.
