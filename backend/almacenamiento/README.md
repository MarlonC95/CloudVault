# Almacenamiento de Dani — fases 01 a 06

Estado al 6 de octubre de 2026: **componentes propios 01–06 implementados/probados**. Ensayo Railway/navegador aprobó PUT/GET/bytes/ETag y limpieza. Inicio/confirmación/descarga instalados; proveedor real, SQL compartido y mantenimiento pendientes. La suite aislada aprobó 237 pruebas. Fase 06 incluye transferencia HTTP local de cinco bytes, sin nueva transferencia Railway.

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
| `descarga.py` / `configuracion_descarga.py` | Autorización, vínculo a publicación, HEAD, firma GET como adjunto y tasa/auditoría durables |
| `validacion.py` | Validadores públicos internos de texto técnico y checksum, compartidos por persistencia y adaptadores |
| `esquema.py` | Inspección de solo lectura de mapping, constraints, índice y triggers |
| `inicio.py`, `configuracion_inicio.py` | Reserva, cuota y firma antes de 201; configuración/fábrica real obligatoria |
| `confirmacion.py` | Reclamo, COPY único, verificación final y confirmación de metadatos externos antes de 200 |
| `verificacion.py`, `verificar_publicacion.py` | Hash final en proceso separado, con tamaño y timeout acotados |
| `views.py`, `urls.py`, `schema.py` | Inicio/confirmación HTTP, parser limitado, errores locales y Swagger JWT |
| `tests/` | Casos positivos, negativos, límites, OpenAPI y seguridad; configuración sin base de datos |
| `tests_persistencia/` | PostgreSQL desechable, SQL literal y pruebas de persistencia/concurrencia/rollback/recuperación |

No hay migraciones propias. Están instaladas inicio, confirmación y descarga en el router del módulo. El cliente S3 es una primitiva interna: no autoriza ni reserva cuota por sí mismo. Las interfaces/adaptadores no implementan modelos, CRUD, planes ni permisos de otros integrantes. La autenticación y su handler global conservan su código. Los cambios compartidos mínimos son el registro de app, boto3 y la inclusión del router propio; no instala SQL al arrancar.

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

Arranca un clúster nuevo sin TCP en `/private/tmp`, instala la copia SQL literal con prerrequisitos exclusivos de prueba y ejecuta persistencia, adaptadores, contrato y seguridad. Verifica la identidad del servidor antes de los tests y lo detiene/elimina al finalizar. No usa `.env` ni la DB de aplicación. No lanzar `tests_persistencia` con otro runner/configuración. El resultado vigente es **281 pruebas aprobadas con PostgreSQL 17.11**. El desglose vigente es 130 sin DB/red externa y 151 con PostgreSQL aislado. Una prueba usa un servidor HTTP loopback exclusivo y cinco bytes; no utiliza la red externa ni valida la criptografía del servidor S3.

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

El contrato exportado identifica las tres operaciones instaladas con integración pendiente. Swagger real publica inicio, confirmación, descarga y auth.

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

Configuración adicional: `ALMACENAMIENTO_MAXIMO_PUBLICACION_BYTES` (por defecto menor de máximo operativo y 5 GiB, normalmente 1 GiB) y `ALMACENAMIENTO_VERIFICACION_SEGUNDOS` (60, máximo 300). El worker hereda entorno S3 cargado, no lee `.env` ni usa SQL. No configurar fixtures. La fase 07 implementa diario y proceso periódico propios, con despliegue/SQL/proveedor pendientes. No hay borrado compensatorio del final.

Integración de negocio/SQL y nuevo COPY en Railway todavía no certificados. El hash acredita los bytes recibidos en el final; el contrato no incluye un checksum esperado del original. PREPARED sin final requiere reconciliación, sin repetir COPY. La cancelación interna y las tareas periódicas propias están implementadas en fase 07; no se añade cancelación pública al contrato.

## Descarga autorizada — fase 06

`GET /api/v1/archivos/{id}/descarga/` responde 200 con `data.url_descarga`, `nombre` y `expira_en` UTC. Usa JWT existente, UUID y proveedor real `autorizar_descarga` de la fábrica obligatoria. Sin proveedor, 503 antes de SQL/S3. El proveedor decide permisos actuales, ámbito y accesibilidad/papelera; no se agregan modelos ni permisos alternativos. Rechaza query/body y POST/HEAD, sin emitir firmas.

`descarga.py` vincula metadatos a sesión CONFIRMED, ledger PUBLISHED y clave final canónica propia. Contrasta organización, tamaño, SHA persistido y ETag/versión finales; no firma temporales ni archivos externos al flujo verificado. Puede descargar otra persona autorizada por el proveedor. HEAD se ejecuta fuera de transacción y verifica existencia/huella; ausencia 404 con advertencia mínima, AccessDenied/timeout/huella distinta 503 seguro. Una segunda autorización detecta revocación o metadatos cambiados antes de firmar.

La firma GET local fuerza attachment, nombre Unicode codificado con fallback ASCII, application/octet-stream y private/no-store; controles/rutas no son admisibles. El vencimiento se calcula exactamente desde fecha/TTL firmados por SDK. La vista devuelve no-store/no-referrer. No almacena URLs en auditoría. Evento DESCARGA_AUTORIZADA con actor/organización y solo archivo_id en detalles, confirmado antes de 200. No cambia cuota ni metadatos de negocio.

Configuración propia: `ALMACENAMIENTO_VIGENCIA_DESCARGA_SEGUNDOS` (300, máximo 300), `ALMACENAMIENTO_DESCARGAS_POR_VENTANA` (30) y `ALMACENAMIENTO_VENTANA_DESCARGAS_SEGUNDOS` (60). Enteros positivos, valores inválidos 503. El límite persiste emisiones aceptadas por actor entre organizaciones bajo advisory lock transaccional PostgreSQL READ COMMITTED; 429 con Retry-After. No cuenta todos los fallos ni limita GET directos al bucket con una URL emitida. No se admite transacción exterior para evitar HEAD bajo locks.

Una URL firmada es una capacidad temporal: quitar permisos impide nuevas emisiones pero no revoca las emitidas; expirar impide iniciar solicitudes, sin cortar transferencias iniciadas. El hash corresponde al final verificado en fase 05; HEAD no prueba criptográficamente los bytes ni impide una sobrescritura externa posterior. Proteger publicaciones de otros escritores y usar VersionId solo cuando haya versión registrada; no asumir versionado Railway. No incluye preview ni enlaces públicos. Falta validar esta ruta con los servicios/SQL/bucket reales.

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


## Cancelación y mantenimiento — fase 07

`mantenimiento.py` coordina cancelación interna por actor UUID, vencimiento y limpieza bajo el reclamo de publicador de fase 05. `ServicioMantenimiento.cancelar` no tiene ruta HTTP nueva: una copia ambigua puede devolver PENDING/pendiente_reconciliacion, y un archivo CONFIRMED no se cancela. La reserva efectiva deja de contar por estado/vigencia sin ajustar el contador usado.

`sql/mantenimiento.sql` define un diario propio en almacenamiento_tecnico, separado de las 13 tablas de referencia. Lo instala Marlon después de revisar dependencias/permisos; ningún comando de runtime instala SQL. El runner lo aplica solo al PostgreSQL desechable. La confirmación actualizada crea el trabajo junto con PREPARED antes de COPY, y guarda ACK de conclusión tras respuesta SDK completa. Si falta el complemento, no se emite esa copia.

El proveedor obligatorio añade `inspeccionar_objeto_tecnico` de `integracion.py`: referencias globales, incluyendo papelera/otros actores, mediante consulta SQL local coordinada. Un 404 de permisos no acredita ausencia. Sin proveedor o conclusión comprobada de un COPY ambiguo, el diario conserva pendiente y no borra. Los escritores compartidos deben respetar el reclamo y prohibir referencias nuevas a claves terminales.

Se limpia solo la clave temporal canónica y, para intentos abandonados no referenciados y concluidos, su final canónico. CONFIRMED/PUBLISHED conserva el final. HEAD/DELETE fuera de transacciones de cuota; timeout de DELETE exige verificar ausencia. Espera hasta expiración más margen, guarda reintentos crecientes y repite barridos de tombstones para recoger PUTs tardíos. VERIFIED/CLEANED acreditan el barrido observado, no ausencia perpetua.

Desde backend, con proveedor y SQL reales preparados:

```bash
.venv/bin/python manage.py mantener_cargas
.venv/bin/python manage.py mantener_cargas --continuo --intervalo 60
```

El modo continuo es la alternativa propia sin Celery/Redis. Debe ejecutarse bajo el supervisor del ambiente; no se ha desplegado ni dejado activo en Railway. `--ciclos N` permite acotar demostraciones. Salida JSON por ciclo con métricas/resultados sanitizados. El intervalo solicitado no garantiza demora máxima si un ciclo/backlog lo supera. Se probó un proceso real de dos ciclos en el clúster aislado.

Valores por defecto: intervalo 60 s, margen 300 s, reintento 60 s hasta 3600 s, barrido de tombstones 3600 s, PREPARED antiguo 3600 s y lote 100 (máximo 1000). Variables: ALMACENAMIENTO_MANTENIMIENTO_INTERVALO, ALMACENAMIENTO_MARGEN_LIMPIEZA_SEGUNDOS, ALMACENAMIENTO_REINTENTO_SEGUNDOS, ALMACENAMIENTO_REINTENTO_MAXIMO_SEGUNDOS, ALMACENAMIENTO_BARRIDO_SEGUNDOS, ALMACENAMIENTO_PREPARADO_ANTIGUO_SEGUNDOS y ALMACENAMIENTO_MANTENIMIENTO_LOTE.

El hito de 281 pruebas incluyó 44 nuevas de fase 07; queda incluido en el resultado vigente de fase 08. Pendiente de integración: diario/permisos SQL, proveedor real de referencias, protocolo común de escritores, evidencia de copias ambiguas sin ACK y ejecución supervisada.

## Pruebas y evidencia — fase 08

313 pruebas del módulo/contrato/SQL/seguridad y 31 de auth compatible aprobaron el 7 de octubre de 2026. Las seis de seguridad de auth se ejecutan en ambos perfiles. [Guía y reproducción](../../agente/pruebas-fase-08.md) · [evidencia](../../agente/evidencia-fase-08.md).

Desde `backend`, `.venv/bin/python -m almacenamiento.tests_persistencia.ejecutar --conservar-temporales --informe ../agente/resultado-fase-08-reinicio-local-final.json` arranca PostgreSQL privado, verifica propiedad, instala referencia literal/complemento, comprueba reinicio y ejecuta toda la suite. No lee `.env` ni prueba contra la DB compartida. Por defecto detiene/conserva el clúster; `--eliminar-temporales` requiere autorización de Dani.

`aceptacion.py` y `ResultadoConEvidencia` producen matriz de 49 casos con IDs ejecutados, estados/duración y expectativas HTTP/SQL/S3/cuota. Un skip, fallo o ID ausente no acredita éxito. `--exigir-integracion` devuelve código 2 mientras falte integración completa.

`--perfil-auth-desplegado --evidencia-entorno-real ...` ejecuta por separado los tests existentes de auth en otra fixture privada con mapping de fecha observado; no cambia producción ni acredita compatibilidad de la referencia literal. `verificar_entorno_real` requiere informe y usa PostgreSQL forzado a solo lectura para consultar metadatos. `consolidar_fase8` conserva fuentes/hashes y no hace red.

El ensayo `.venv/bin/python -m almacenamiento.probar_s3 --ejecutar --perfil railway --conservar-objetos --seguridad-fase8 --navegador --informe ...` usa `.env` restaurado y Railway real. Verifica bytes/hash, firmas/headers/host adversos y estabilidad del final; navegador prueba CORS/ETag. Por defecto conserva objetos y registra claves nuevas para localizar el ensayo; `--limpiar-objetos` solo con petición explícita. `--sin-env` permite un entorno ya preparado, sin mezclar credenciales de perfiles.

La conexión real aprobó, pero falta la factory de negocio en `.env` y el diario de mantenimiento en DB real. `usuarios.fecha_creacion` existe en despliegue y `creado_en` en referencia; alineación pendiente. COPY Railway no rechazó ETag distinto ni devolvió versión. F04/reconstrucción y flujo integrado del equipo pendientes. El controlador MinIO opcional exige autorización explícita de limpieza; la corrida vigente usa Railway y conserva datos.
