# Evidencia de fase 03 — cliente S3 y ensayo aislado

Fecha: 5 de octubre de 2026, America/Guatemala. Rama inicial/final: `feature/minio-presigned-urls`. HEAD de referencia: `c2e5a27` (`Update .gitignore`). Cambios de esta intervención locales, sin commit, push, merge ni despliegue.

**Estado:** implementación propia y pruebas locales aprobadas. Integración Railway pendiente: las credenciales efectivamente cargadas de `backend/.env` recibieron `403 InvalidAccessKeyId`. No se certifica transferencia, copia, CORS, privacidad ni expiración reales del bucket.

## Implementación comprobada

Configuración con perfiles independientes `AWS_*` (Railway) y `S3_*` (MinIO), selección explícita, sin fallback, secretos excluidos de repr, validación de endpoint/TLS y estilo de URL. El `S3_BUCKET` histórico del `.env` difiere de `AWS_STORAGE_BUCKET_NAME`; no se cambió el archivo privado ni se mezclaron destinos.

Cliente SigV4 con firma PUT/GET, consulta HEAD, hash real por bloques y límite de lectura, copia condicional con validación de respuesta/HEAD y borrado técnico idempotente. Claves propias canónicas UUID y rechazo de firma PUT sobre publicaciones o claves ajenas. Errores SDK sanitizados, distinción 403/404, timeout de 5/15 s y máximo de tres intentos.

Ensayo opt-in con claves únicas, contenido sintético, limpieza en finally, verificación de ausencia y código de salida distinto de cero ante flujo incompleto. Página propia de ensayo de navegador y contenedor propio de pruebas con contexto selectivo, sin `.env`, sin red ni acceso a sistemas compartidos.

## Pruebas ejecutadas

| Verificación | Resultado y límite |
|---|---|
| Suite local sin `.env`/DB/red | **70 pruebas aprobadas**, 0 fallidas, comprobaciones Django sin incidencias |
| Regresión con PostgreSQL aislado | **115 pruebas aprobadas**, 0 fallidas; PostgreSQL 17.11, servidor nuevo privado en `/private/tmp`, esquema de referencia de 13 tablas con prerrequisitos sintéticos; detenido y eliminado al finalizar |
| Docker Compose | Configuración validada; imagen construida desde `python:3.14.7-slim`; **70 pruebas aprobadas** como usuario 10001, filesystem de solo lectura, sin red, sin volúmenes ni secretos |
| CLI independiente | `--help` funciona sin iniciar Django ni cargar `.env`; ejecución sin `--ejecutar` se rechaza antes de construir cliente |
| Higiene de cambios | `git diff --check` aprobado; cambios compartidos limitados a añadir boto3 en `backend/requirements.txt` |

Las 115 pruebas incluyen las 70 de contrato/seguridad/S3 y 45 de persistencia/frontera compartida. Las 26 pruebas nuevas son 21 de cliente/configuración y 5 del ensayo. Las 70 de Docker repiten la suite local sin DB: no deben sumarse como casos distintos a las 115. No se prueban ACL reales ni servicios de German por estas suites.

Ambiente local: Python 3.14.7, Django 5.2.17, DRF 3.18.1, boto3 y botocore 1.43.108. SDK instalado en `backend/.venv`; pin de boto3 en `requirements.txt`. Base de imagen Docker resuelta a `sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d`. El build envió un contexto selectivo de aproximadamente 243 kB. La imagen final se construyó correctamente; no se desplegó.

Las líneas `Internal Server Error` de auth corresponden a errores sintéticos inyectados por sus pruebas existentes de confidencialidad, que aprobaron. No se modificó auth. El primer intento del runner PostgreSQL encontró la restricción de memoria compartida del sandbox; la ejecución aislada autorizada posteriormente aprobó. Docker Desktop se inició para ejecutar el contenedor de pruebas.

## Acceso Railway realmente observado

Se usó `.env` con las variables que Dani indicó, sin imprimir sus valores ni reutilizar claves del texto del chat. Se autorizaron ensayos exclusivamente con claves nuevas propias, sin listar, cambiar CORS/políticas ni tocar archivos de negocio.

1. Ensayo PUT firmado: respuesta negativa; el ensayo terminó antes de HEAD/COPY/GET/CORS y no inició el servidor del navegador. La limpieza/ausencia no pudo certificarse porque el acceso también fue rechazado. Informe inicial sanitizado en `/private/tmp/cloudvault-fase03-railway.json`, prueba `e9a91c62-fd64-43c9-8c52-f9e2432711fc`.
2. HEAD sobre claves UUID inexistentes, tanto con estilo virtual como path: **403** en ambos casos. No se trató como objeto inexistente ni éxito.
3. Diagnóstico de PUT con una clave temporal nueva: **403, `InvalidAccessKeyId`**. Se extrajo solo el código permitido del XML en memoria; no se imprimieron cuerpo, firma ni valores privados. La carga no fue aceptada.

Esto demuestra respuesta del proveedor y rechazo de la identidad de acceso, no conectividad funcional autorizada. Se solicitó a Dani actualizar el par vigente en `.env` y avisar; no se pidió pegar secretos en el chat. No se cambió bucket ni se intentó arreglar el problema modificando permisos ajenos.

## Pendiente para cerrar fase 03

- Repetir el ensayo con el par de credenciales que Railway acepte para el bucket seleccionado.
- Verificar PUT/HEAD/COPY/GET/DELETE con comparación del contenido real y ausencia después de limpieza.
- Registrar precondiciones de copia, checksum y versiones efectivamente soportadas. Si la condición no se cumple, fase 05 necesita una alternativa verificable antes de publicar.
- Verificar GET anónimo denegado y rechazo de PUT/GET vencidos.
- Ejecutar el HTML de ensayo en navegador y comprobar PUT/GET reales, CORS y lectura de ETag. No modificar React de Mily ni política CORS sin una asignación correspondiente.

El contenedor y la configuración propia ya quedaron probados. Los endpoints, cuotas reales, confirmación de metadatos y mantenimiento siguen en fases 04–07. MinIO tiene firmas/configuración probadas offline, sin transferencia real acreditada. Referencias consultadas: [Railway Storage Buckets](https://docs.railway.com/storage-buckets), [Boto3 generate_presigned_url](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/generate_presigned_url.html), [CopyObject](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/copy_object.html).

## Archivos de esta intervención

- Nuevos: `backend/almacenamiento/configuracion_s3.py`, `s3.py`, `probar_s3.py`, `ensayo_s3.html`, `tests/test_s3.py`, `tests/test_ensayo_s3.py`, `infra/Dockerfile`, `infra/Dockerfile.dockerignore`, `infra/compose.yaml`.
- Modificados propios: `backend/almacenamiento/errores.py` (import diferido de handler para usar S3 sin iniciar Django), `backend/almacenamiento/README.md`.
- Cambio compartido: `backend/requirements.txt`, únicamente `boto3==1.43.108`.
- Documentación propia: `agent.md`, `agente/README.md`, `agente/fase-03-bucket-y-cliente-s3.md`, `agente/cliente-s3-fase-03.md`, este archivo.

Sin cambios de esta intervención en `config/settings.py`, router, auth, frontend, modelos/CRUD/planes de German, SQL, datos compartidos, `.env` ni referencias literales. La carpeta `agente/` está ignorada por el `.gitignore` actual: sus documentos existen localmente y no se cambiaron las reglas de Git ni se añadieron automáticamente a staging.

## Preparación del commit de fase 03

Se verificó la conservación de los archivos después de resolver los conflictos y volver a `feature/minio-presigned-urls`. Para que las pruebas y Docker funcionen en una copia nueva, se incluyen únicamente la referencia OpenAPI, la copia literal del esquema SQL y la guía/evidencia de fase 03 mediante excepciones precisas de `.gitignore`. El resto de `agente/`, `agent.md`, auditorías, Obsidian, `.env` y datos privados permanecen excluidos. La conexión Railway sigue pendiente por `403 InvalidAccessKeyId`; el commit no certifica integración remota ni despliegue.
