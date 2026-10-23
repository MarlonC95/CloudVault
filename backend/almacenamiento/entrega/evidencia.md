# Evidencia de documentación e integración — fase 09

Fecha: **7 de octubre de 2026**. Rama: `feature/minio-presigned-urls`. Base: `23db3b3` (implementación de fases 07–08). Cambios de esta fase en el árbol de trabajo, sin staging/commit/push/despliegue. [Guía de integración](README.md) y [dependencias por responsable](dependencias.md).

## Resultado vigente

**327/327 tests aprobados en 10.599 s**: 313 anteriores y **14 nuevos de fase 09** (10 de entrega/contrato/cliente y cuatro de recorrido SQL). Python 3.14.7, Django 5.2.17, PostgreSQL 17.11 (`170011`). Inicio del informe: `2026-10-07T14:01:13.737227+00:00`.

Ejecución: `almacenamiento.tests_persistencia.ejecutar --conservar-temporales`. Instala en PostgreSQL privado la referencia literal de 13 tablas y complemento técnico; confirma reinicio y detiene/conserva el clúster. No usa `.env` ni DB Railway. Informe íntegro de trabajo: `agente/resultado-fase-09-local-final-v2.json`; log: `/private/tmp/cloudvault-fase09-local-final-v2.log`. [Resumen portable y huellas](verificacion.json).

| Verificación | Evidencia ejecutada | Límite |
|---|---|---|
| OpenAPI y Swagger | Documento válido; comparación de tres rutas, cuerpos estrictos, UUID, status y headers | Perfil operativo por defecto; no despliegue |
| JSON de ejemplos | Validación de bodies/salidas ficticias contra el esquema | No son firmas ni identidades vigentes |
| Errores de vistas | 400/401/405/503, código/fields y headers, auth existente sin DB para invalidación | Proveedor ausente deliberado y actor autorizado sustituido en los casos que lo necesitan |
| Cliente sobre vistas/SQL | Inicio 201, PUT sintético, confirmación 200 repetida idéntica, autorización 200, GET y hash exactos de 17 bytes | Actor autorizado/negocio/bucket son dobles declarados; no React ni login real |
| Persistencia | CONFIRMED/PUBLISHED, una copia/archivo, usado aumenta 17 exactamente una vez | Fixture con autoridad de uso sintética; no valida trigger desplegado |
| ETag opcional | Sin ETag expuesto, confirmación `{}` válida | No exige cambiar CORS ni inventa checksum |
| Fallo de confirmación | Conserva archivo_id, una sesión PENDING, sin recopy ni DELETE | No resuelve proveedor/mantenimiento externo |
| GET incorrecto | Bytes distintos producen fallo, no aprobación | Bucket sustituido intencionalmente |
| Transporte HTTP real | Loopback: bytes binarios, ETag, 302 sin seguir destino, respuesta excesiva rechazada | No prueba TLS/CORS remoto; listener propio cerrado al terminar |
| Confidencialidad/guardas | No JWT a storage; URL ajena y configuración inválida rechazadas; excepciones saneadas; flag obligatorio | No es prueba de UI React |

El contrato exportado ahora incluye 405, elimina 429 de confirmación, describe headers reales y comparte fragmentos estrictos con drf-spectacular. El esquema propio marca obligatorio el body de inicio y permite body opcional de confirmación. No se cambia el formato ni la lógica de negocio de los endpoints.

Se conservan los intentos anteriores. El primer test de contrato detectó que drf-spectacular marca opcionales los bodies dict; se corrigió mediante `EsquemaAlmacenamiento`, limitado a vistas de Dani. Una fixture de test intentaba logout y requería la app de sesiones ausente; se corrigió creando un APIClient nuevo por operación, sin modificar auth/settings compartidos. La corrida posterior aprobó 326 casos; la final añade el caso de transporte HTTP real y aprueba 327. No se borraron logs, informes ni clústeres.

## Evidencia real reutilizada de fase 08

Corrida Railway `d4d8158d-ab67-46df-8806-1bc332393bd5`, `2026-10-07T06:07:07.929790+00:00`: PUT/HEAD/GET/hash/COPY y navegador PUT/GET/bytes/ETag aprobados, así como denegación de firmas vencidas/alteradas y MIME adverso. Cinco objetos conservados. COPY con ETag adverso **no fue rechazado** y no devolvió versión. Host adverso devolvió 404 de ruta, sin demostrar un mecanismo interno de firma.

La conexión PostgreSQL real de fase 08 fue de solo lectura, con metadatos: 13 tablas por nombre, falta diario técnico, existe `fecha_creacion` y no `creado_en`; factory de negocio no configurada. No se inspeccionó toda autoridad/triggers del despliegue. La regresión auth de **31 casos** corresponde al perfil privado compatible de fase 08; no se volvió a ejecutar ni equivale a compatibilidad de la referencia literal. La suite actual conserva el diagnóstico del choque de fecha.

No se repitió la transferencia Railway, se instaló SQL compartido, se cambió CORS ni se ejecutó mantenimiento real en fase 09. `.env` verificado intacto por huella; no se publican valores ni la huella privada en la entrega. Los hashes de fuentes anteriores están en `verificacion.json` para distinguir evidencia histórica de pruebas actuales.

## Cierre del alcance propio

OpenAPI, ejemplos ejecutables, guía de headers/UTC/reintentos/cancelación/errores, README de instalación/configuración/mantenimiento y dependencias quedan listos para revisión independiente de la conversación. Ningún archivo React, CRUD, suscripciones, auth o SQL de referencia fue modificado por Dani en esta fase.

**Integración conjunta pendiente:** proveedor de German, instalación/revisión SQL por Marlon, alineación de mapping/autoridad de cuota, supervisor compartido, CORS del origen definitivo y ejecución con Mily/React. F04 de fase 08 tampoco se certifica. El resumen marca `integracion_react_certificada: false` e `integracion_equipo_certificada: false` aunque todos los tests locales aprueben.
