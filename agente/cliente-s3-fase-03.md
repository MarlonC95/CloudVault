# Cliente S3 de Dani — fase 03

Fecha: 5 de octubre de 2026, America/Guatemala. Implementación en `backend/almacenamiento/`; no monta endpoints ni accede a SQL. La autorización y reserva se incorporan en fase 04; publicación verificable en fase 05; descarga autorizada en fase 06.

## Configuración

El módulo no lee `.env` al importarse. Django ya carga `backend/.env` en su configuración existente; el ensayo independiente lo carga explícitamente con django-environ. Variables del proceso prevalecen sobre el archivo. No hay credenciales literales en los archivos nuevos.

| Perfil | Variables obligatorias | Opcionales |
|---|---|---|
| `railway` (predeterminado) | `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `AWS_S3_URL_STYLE=virtual` o `path` |
| `minio` | `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | `S3_PUBLIC_ENDPOINT_URL`, `S3_URL_STYLE=path` o `virtual` |

Elegir con `ALMACENAMIENTO_PERFIL` o `ConfiguracionS3.desde_entorno(perfil=...)`. No se mezclan nombres entre perfiles; no existe fallback de `AWS_STORAGE_BUCKET_NAME` a `S3_BUCKET`. Esto permite mantener el `S3_BUCKET` histórico del `.env` sin que cambie el destino Railway solicitado por Dani. Los valores del perfil no seleccionado quedan inactivos. Variables faltantes, URLs con credenciales/path/query, estilos desconocidos y buckets inválidos se rechazan, sin imprimir valores.

Railway exige HTTPS y un único endpoint. MinIO permite HTTP en el perfil local explícito y un endpoint público distinto para firmar. Siempre se verifica TLS en conexiones HTTPS. El host no se reescribe después de firmar. El perfil MinIO tiene pruebas offline de generación de firmas, pero no acredita una transferencia MinIO real.

## Primitivas disponibles

```python
from almacenamiento.configuracion_s3 import ConfiguracionS3
from almacenamiento.s3 import ClienteS3, nueva_clave_temporal

cliente = ClienteS3(ConfiguracionS3.desde_entorno(perfil="railway"))
try:
    clave = nueva_clave_temporal()
    # El coordinador debe haber autorizado y persistido la reserva primero.
    firma = cliente.firmar_put(clave, "application/pdf")
finally:
    cliente.cerrar()
```

- `firmar_put`: solo claves técnicas temporales/de ensayo; nunca publicaciones. Firma Content-Type y devuelve método, headers y vencimiento UTC. Máximo 900 segundos, configurable con `PoliticaCarga`.
- `firmar_get`: clave entregada por el coordinador después de autorización; máximo 300 segundos. El cliente no implementa ACL.
- `consultar`: HEAD con tamaño, MIME declarado, ETag y evidencia opcional del proveedor. 404 se distingue de 403; HEAD no prueba el tipo real ni el hash.
- `verificar_contenido`: GET interno por bloques con límite estricto, calcula SHA-256 hexadecimal del contenido completo y cierra el stream incluso ante error/exceso. No transmite binarios de subida por Django ni calcula previews.
- `copiar`: claves técnicas propias, origen distinto del destino, `CopySourceIfMatch`, resultado de copia y HEAD final. No acredita que el proveedor respete la precondición; el ensayo negativo debe comprobarlo y fase 05 verificar bytes antes de publicar metadatos.
- `borrar_tecnico`: solo claves canónicas generadas bajo `cloudvault/dani/temporales|publicaciones|pruebas`; idempotente ante ausencia. El coordinador de fase 07 deberá demostrar que una publicación no está vigente antes de borrarla. No es un endpoint para borrar archivos de negocio.

Las claves generadas llevan UUID y caben en 255 caracteres. No se usa el nombre de archivo como clave. ETag, checksum SHA-256 Base64 del proveedor y SHA-256 hexadecimal calculado son datos distintos. PUT firmado no prueba tamaño/MIME real, puede reutilizarse antes de vencer y no apunta a la clave final. No se presupone versionado, Object Lock, lifecycle ni cifrado de aplicación.

Los errores SDK se traducen a `ErrorS3` con tipos fijos, sin XML, URL, secretos ni traceback en la respuesta. Ausencia usa `NO_ENCONTRADO`; acceso S3 denegado, precondición, caída y lectura inválida usan `SERVICE_UNAVAILABLE` como frontera interna. El coordinador debe resolverlos según el contexto; un 403 del bucket no se convierte en un permiso de usuario concedido/denegado por German. No habilitar logs DEBUG de boto3/botocore/HTTP con credenciales reales. SDK usa SigV4, connect/read de 5/15 segundos y hasta tres intentos estándar.

## Reproducción

Desde `backend/`, instalar `requirements.txt` en el entorno propio. El SDK añadido es `boto3==1.43.108`.

Pruebas sin `.env`, red ni DB:

```bash
.venv/bin/python -m django test almacenamiento.tests auth_workspaces.tests.test_error_security --settings=almacenamiento.tests.settings --verbosity=1
```

Regresión de persistencia con PostgreSQL desechable, sin `.env` ni base compartida:

```bash
.venv/bin/python -m almacenamiento.tests_persistencia.ejecutar
```

Ensayo Railway explícito con el `.env` vigente (crea textos sintéticos y limpia solo sus nuevas claves):

```bash
.venv/bin/python -m almacenamiento.probar_s3 --ejecutar --perfil railway --navegador --informe /private/tmp/cloudvault-fase03-railway.json
```

El ensayo usa `cloudvault/dani/pruebas/<UUID>/<UUID>`; no lista objetos, no crea buckets, no cambia CORS ni modifica objetos existentes. Hace PUT/HEAD/GET, compara hash/bytes, copia positiva/negativa, sondea checksum, verifica acceso anónimo y vencimiento y repite borrado con HEAD para demostrar ausencia. El informe guarda solo indicadores, estados HTTP y UUID del ensayo; nunca URLs/credenciales. Fallos de capacidades opcionales se registran; fallos del flujo esencial o limpieza devuelven código de salida distinto de cero. Un fallo después de una operación de resultado incierto requiere repetir la limpieza de esas claves propias, sin tocar otras.

Con `--navegador`, abre `http://127.0.0.1:8765` y pulsa **Probar carga directa**. El servidor efímero escucha solo localhost durante un máximo de 180 segundos. Las URLs se entregan en memoria, sin cache ni logs de acceso; el navegador sube un texto propio y compara su descarga. Este HTML es un cliente de ensayo de Dani, no un componente React de Mily. CORS y exposición de ETag se informan por separado. Sin `--navegador`, el ensayo HTTP no certifica CORS en navegador.

Contenedor propio, desde la raíz:

```bash
docker compose -f backend/almacenamiento/infra/compose.yaml build pruebas
docker compose -f backend/almacenamiento/infra/compose.yaml run --rm pruebas
```

El contexto se limita con `Dockerfile.dockerignore` al código necesario y el OpenAPI de diseño. No envía `.env`, `.git`, frontend, SQL ni documentación ajena al daemon. No monta secretos, corre sin red, como usuario sin privilegios y con filesystem de solo lectura. No despliega el backend ni sustituye los contenedores del equipo.

Referencias técnicas consultadas: [Railway Buckets](https://docs.railway.com/storage-buckets), [firma de URLs de boto3](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/generate_presigned_url.html), [CopyObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/copy_object.html). Compatibilidad real debe probarse contra el proveedor; consultar [evidencia](evidencia-fase-03.md).
