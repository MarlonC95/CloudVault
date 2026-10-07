# Integración de almacenamiento — entrega de Dani a Mily

Referencia vigente: `Contratos de API - CloudVault.pdf`, preservado en `agente/referencias/contrato-api-vigente.pdf`. SHA256: `6eeff62ae63321a75cdab221c25d7855fd8a964034e4ed4f1f3c490aa7f3e059`. `docs/CONTRATO_API.md` está descartado por decisión de Dani. Este paquete documenta las tres rutas de Dani existentes; no añade rutas de estado, cancelación pública, listado, planes, refresh, logout o vista previa.

## Archivos y estado de integración

| Entregable | Uso |
|---|---|
| [openapi.json](openapi.json) | Importable en herramientas OpenAPI; generado desde el mismo contrato de Swagger |
| [ejemplos.json](ejemplos.json) | Peticiones y respuestas ficticias válidas, sin tokens ni firmas vigentes |
| [cliente_integracion.py](../cliente_integracion.py) | Ejemplo ejecutable de seis solicitudes, sin dependencias adicionales ni cambios React |
| [dependencias.md](dependencias.md) | Interfaces y condiciones pendientes para German, Marlon y Mily |
| [evidencia.md](evidencia.md) | Qué se probó, ambiente, resultados y límites de la entrega |

Las vistas y el cliente se prueban contra PostgreSQL privado con proveedor de negocio, bucket y actor autorizado sustituidos explícitamente. Fase 08 acreditó Railway S3/CORS desde el navegador y conexión SQL de solo lectura. El flujo completo con proveedor real, SQL compartido y React de Mily sigue pendiente. La presencia de una ruta en Swagger no acredita su despliegue.

## Preparar el backend

Desde `backend/`, utilizar Python y el entorno virtual de la instalación. Instalar `requirements.txt` si el ambiente aún no tiene sus dependencias. El módulo ya está conectado al router y a `drf-spectacular`; no requiere nuevas librerías para el cliente.

Conservar `backend/.env`; no reemplazarlo por ejemplos. La aplicación lo carga mediante su configuración existente. Ni el cliente ni los tests privados lo leen. Marlon instala y revisa el esquema de 13 tablas y el complemento [sql/mantenimiento.sql](../sql/mantenimiento.sql), función de timestamps, rol y permisos; `managed=False` y las migraciones Django no los instalan. Auth y SQL deben usar el mismo mapping de fechas. Confirmación usa PostgreSQL directo o pool de sesiones, con READ COMMITTED; un pool de transacciones no conserva el reclamo de publicador.

Configurar una fábrica **real** compatible con [integracion.py](../integracion.py) mediante `ALMACENAMIENTO_SERVICIOS_FACTORY`, con alias SQL `default`. No apuntar a fixtures de `tests_persistencia`. Sin la fábrica válida, la API devuelve 503 sin firmar. Mantenimiento y confirmación necesitan el diario técnico instalado; no aplicar SQL a Railway desde este cliente.

| Configuración | Valor por defecto o condición |
|---|---|
| `ALMACENAMIENTO_PERFIL` | `railway`; perfil `minio` independiente |
| `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Obligatorios para Railway, gestionados como secretos; no entregarlos al frontend |
| `AWS_S3_URL_STYLE` | `virtual`; `path` solo si corresponde al bucket configurado |
| `S3_ENDPOINT_URL`, `S3_PUBLIC_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_URL_STYLE` | Solo MinIO; endpoint público para firma, estilo `path` por defecto; sin fallback AWS |
| `ALMACENAMIENTO_MAXIMO_ARCHIVO_BYTES` | 1073741824 (1 GiB), entero positivo; cuota organizacional adicional |
| `ALMACENAMIENTO_MAXIMO_PUBLICACION_BYTES` | Menor entre máximo operativo y 5 GiB; no superar 5 GiB |
| `ALMACENAMIENTO_VIGENCIA_CARGA_SEGUNDOS` | 900, máximo 900; puede acortarse por el período de cuota |
| `ALMACENAMIENTO_VIGENCIA_DESCARGA_SEGUNDOS` | 300, máximo 300 |
| `ALMACENAMIENTO_INICIOS_POR_VENTANA`, `ALMACENAMIENTO_VENTANA_INICIOS_SEGUNDOS` | 10 inicios aceptados por actor cada 60 s |
| `ALMACENAMIENTO_DESCARGAS_POR_VENTANA`, `ALMACENAMIENTO_VENTANA_DESCARGAS_SEGUNDOS` | 30 emisiones GET aceptadas por actor cada 60 s |
| `ALMACENAMIENTO_VERIFICACION_SEGUNDOS` | 60, máximo 300; hash en proceso acotado |
| Mantenimiento | Intervalo 60, margen 300, reintento 60–3600, barrido 3600, PREPARED antiguo 3600 segundos; lote 100, máximo 1000 |

Las variables específicas del último renglón están en [configuracion_mantenimiento.py](../configuracion_mantenimiento.py) y el [README del módulo](../README.md). OpenAPI entregado documenta el perfil por defecto. Al cambiar el máximo operativo, exportar `crear_openapi(politica=...)` para ese perfil y validar su correspondencia; las respuestas reales prevalecen para método, headers y vencimiento. Railway no rechazó COPY con ETag adverso ni devolvió versión en el ensayo de fase 08; no depender de esas garantías.

## Peticiones a Django

Base de API significa el **origen**, por ejemplo `https://api.example.invalid`, sin `/api/v1`. Swagger existente está en `/api/docs/`; el esquema completo, incluida auth, en `/api/schema/`. El archivo entregado contiene exclusivamente las rutas de Dani.

Enviar `Authorization: Bearer <access temporal>` y `Accept: application/json` a Django; para los POST con JSON, `Content-Type: application/json`. Usar el login existente `/api/v1/auth/login/` con sus campos actuales `correo` y `contrasena`; tomar `data.tokens.access`. El access por defecto dura 15 minutos. Aunque login devuelve refresh, no existe una ruta de refresh en el router revisado. Ante 401 volver al flujo de sesión disponible, sin inventar refresh ni desactivar permisos.

| Ruta | Body | Éxito |
|---|---|---|
| `POST /api/v1/archivos/iniciar-carga/` | `nombre`, `tamano_bytes` entero, `tipo_mime`, `carpeta_id` UUID opcional/null | 201 con `data.archivo_id`, `url_subida`, `metodo`, `encabezados`, `expira_en` |
| `POST /api/v1/archivos/{id}/confirmar-carga/` | `{}` o `{"etag":"\"valor literal\""}`; cuerpo omitido también admitido | 200 con `data.id`, `nombre`, `es_nuevo`, `en_papelera` |
| `GET /api/v1/archivos/{id}/descarga/` | Sin body ni query | 200 con `data.url_descarga`, `nombre`, `expira_en` |

`id` es el **archivo_id** devuelto por inicio, no el ID interno de sesión. Guardarlo durante el flujo. El body no admite `bucket`, claves S3, organización elegida arbitrariamente, checksum ni campos extra. No hay header Idempotency-Key obligatorio ni deduplicación de inicio por ese header. Nombres sin rutas/controles, de hasta 255 caracteres; MIME tipo/subtipo hasta 100; JSON hasta 16 KiB. Un archivo vacío puede admitirse si la política/cuota lo permiten. La capacidad es organizacional: raíz sin carpeta solo funciona cuando el proveedor resuelve un ámbito inequívoco.

## Subir y confirmar

1. Iniciar una vez y conservar la respuesta en memoria. `expira_en` es ISO 8601 UTC, con `Z` o desplazamiento UTC. Compararlo con hora actual UTC, no con texto de hora local. No añadir arbitrariamente 900 s: el SDK/período pueden acortar el vencimiento.
2. Ejecutar el método recibido, normalmente PUT, sobre **url_subida completa sin modificarla**. Enviar los bytes originales como body binario, usando exactamente `encabezados`. No usar `multipart/form-data` ni envolver los bytes en JSON. No reenviar Authorization/JWT, cookies de Django o access keys al bucket. Host, query, MIME y headers firmados no se editan.
3. PUT 200 acredita transferencia; todavía no acredita publicación ni cuota/listado actualizados. Si CORS expone ETag, conservar el texto completo, incluidas sus comillas, y enviarlo opcionalmente. Si no es legible, confirmar con `{}`. No tratar ETag como SHA256.
4. Confirmar con el mismo `archivo_id`. Solo después de 200 incorporar el resultado confirmado y consultar las APIs reales de listado/cuota de German. `es_nuevo` no es un indicador de primer intento HTTP: la repetición devuelve el mismo resultado durable.

Las respuestas de Django incluyen `Cache-Control: no-store` y `Referrer-Policy: no-referrer`. Mantener las URLs firmadas en memoria; no copiarlas a logs, capturas, localStorage o informes. Para PUT/GET desde el navegador, API CORS y storage CORS son configuraciones diferentes. El bucket debe permitir el origen **exacto** del frontend, PUT/GET, `content-type` y exposición de ETag. En fase 08 se verificó `http://127.0.0.1:8765`; eso no acredita el origen definitivo de React. No aplicar cambios CORS sin autorización de ese ambiente.

## Descargar

Pedir la autorización GET a Django con JWT y usar literalmente `url_descarga` en storage, sin JWT. La firma fuerza descarga adjunta y octet-stream; no se entrega vista previa. Unicode del nombre ya se codifica desde el backend; no reconstruir Content-Disposition en la firma. Al vencer, solicitar una autorización nueva con el mismo archivo, según permisos vigentes. Un lector autorizado puede descargar aunque no sea el autor de la carga.

El límite de descarga cuenta emisiones aceptadas de URL, no GET directos al bucket. Una URL ya emitida permanece como capacidad temporal; quitar permisos no garantiza revocación instantánea y el vencimiento no corta transferencias iniciadas. HEAD de backend no protege frente a escrituras externas: el equipo debe coordinar la inmutabilidad de publicaciones.

## Fallos, reintentos y cancelación

El módulo devuelve `{"error":{"code":"...","fields":{}}}`. `fields` puede contener listas de errores; no interpretar un mensaje SQL/S3 externo ni inventar otros campos. Confirmación no documenta 429; descarga no documenta 409. Auth conserva su propio formato existente.

| HTTP/código | Acción de integración |
|---|---|
| 400 `VALIDATION_ERROR` | Revisar campos, ID, estado y vencimiento; no repetir la misma entrada inválida en bucle |
| 401 `NO_AUTENTICADO` / `TOKEN_INVALIDO` | Recuperar sesión con el mecanismo existente; conservar identidad del flujo |
| 403 `SIN_PERMISO` | Revisar permisos/destino con German; no probar destinos al azar |
| 404 `NO_ENCONTRADO` | Recurso no accesible/en papelera o no disponible; no deducir existencia por otro usuario |
| 405 `VALIDATION_ERROR` | Corregir método; descarga rechaza POST/HEAD, inicio y confirmación requieren POST |
| 409 `CUOTA_EXCEDIDA` | Revisar usado + reservas pendientes con el plan real; no repetir ni codificar “ilimitado” |
| 429 `RATE_LIMITED` | Esperar `Retry-After` cuando esté presente; acotar intentos sin crear sesiones adicionales |
| 500 `ERROR_INTERNO` | Conservar ID y reportar etapa/status/código sin secretos; investigar la causa |
| 503 `SERVICE_UNAVAILABLE` | Dependencia/configuración o publicación ambigua; preservar ID y reconciliar |
| Error de red / respuesta perdida | Determinar qué etapa ocurrió; no tratarlo automáticamente como operación revertida |

Inicio no es idempotente: si se pierde su 201, no se conoce la identidad y no se debe reiniciar automáticamente. No existe endpoint público de consulta para resolverlo. Confirmación puede repetirse con el **mismo ID y el mismo ETag/body** tras recuperar la sesión; reautoriza y devuelve el resultado durable. PREPARED puede representar COPY ya enviada: un 503 no autoriza recopy, DELETE ni nueva publicación. Definir espera/intentos acotados con el responsable; el cliente de ejemplo termina al primer fallo para conservar la evidencia.

Abortar PUT en el navegador no cancela una reserva en servidor. No hay ruta HTTP de cancelación/estado; la cancelación disponible es interna en `ServicioMantenimiento.cancelar`. Mily puede abortar la petición y mostrar estado pendiente; la reserva efectiva termina según estado/vigencia y el mantenimiento de servidor reconcilia cuando esté instalado y autorizado. No crear `/cancelar/` ni llamar a APIs internas desde React.

## Ejecutar el ejemplo

Usar un usuario, carpeta y API de **ensayo aislado previamente preparados**. El cliente crea un archivo de 17 bytes `CloudVault fase 9`, conserva objetos y metadatos, y no lee `.env`. Preparar `ALMACENAMIENTO_TOKEN_PRUEBA` en el entorno con un access temporal; no poner el token en argumentos, archivos o ejemplos. Sustituir los placeholders y usar el origen exacto de la URL firmada; en virtual-hosted incluye el subdominio del bucket.

```bash
python -m almacenamiento.cliente_integracion --ejecutar \
  --base-api https://api.example.invalid \
  --origen-storage https://storage.example.invalid \
  --carpeta-id 11111111-1111-4111-8111-111111111111 \
  --informe almacenamiento/resultados_pruebas/cliente-fase09.json
```

`example.invalid` es ficticio; este comando requiere valores del ambiente preparado y el directorio del informe existente. Para HTTP local solo se acepta loopback; API y storage deben tener orígenes diferentes. No hay redirecciones ni reintentos automáticos. Timeout por solicitud: 15 s; respuesta acotada a 64 KiB. El informe contiene resultado, etapa/código cuando falla y archivo_id si se recibió, hash/bytes cuando aprueba; no contiene token, body, claves S3 o URLs firmadas. Exit 0: recorrido completo; exit 1: fallo; sin `--ejecutar`: exit 2 antes de construir transporte.

La secuencia ejecuta inicio → PUT → confirmación → misma confirmación → autorización de descarga → GET/bytes/hash. El GET debe devolver exactamente los bytes originales. El cliente nunca ejecuta DELETE ni libera reservas como compensación. En el ambiente actual falta el proveedor real: una ejecución contra API compartida no se presenta como demostración aprobada.

## Verificar sin tocar Railway

Desde `backend`, con `initdb`/`pg_ctl` de la misma instalación:

```bash
.venv/bin/python -m almacenamiento.tests_persistencia.ejecutar \
  --conservar-temporales --informe almacenamiento/resultados_pruebas/fase09-local.json
```

Preparar primero el directorio local de informes. Se crea PostgreSQL privado, se instala referencia literal y complemento de prueba, se comprueba reinicio y se ejecutan tests del cliente/contrato/persistencia. Se detiene y **conserva** el clúster. Negocio, actor autorizado y bucket de los nuevos tests son dobles declarados; no acredita login, React ni SQL compartido. La discrepancia de auth con la referencia literal se reproduce como diagnóstico. No ejecutar `--eliminar-temporales` ni limpieza real sin petición explícita de Dani.

Exportar de nuevo el contrato, sin red:

```bash
.venv/bin/python -m almacenamiento.openapi --output almacenamiento/entrega/openapi.json
```

La referencia de tests `agente/contrato-fase-01.openapi.json` también debe quedar sincronizada al modificar el contrato. Para mantenimiento, una vez que el ambiente, dependencias y **eliminación de objetos técnicos** estén expresamente autorizados, los comandos disponibles son `python manage.py mantener_cargas` o `python manage.py mantener_cargas --continuo --intervalo 60`. No se ejecutan como parte del cliente ni de esta entrega; el modo continuo necesita supervisor. Documentar frecuencia/backlog reales antes de certificarlo.
