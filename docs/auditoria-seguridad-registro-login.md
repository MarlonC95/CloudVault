# Resumen de seguridad de registro e inicio de sesión

Auditoría realizada el 24 de septiembre de 2026. Redacción para publicación revisada el 25 de septiembre de 2026.

## Alcance

Se revisaron el registro, el inicio de sesión, las validaciones, el almacenamiento de credenciales, los JWT, el manejo de errores y la integración de autenticación del frontend. La recuperación se consideró para comprobar la invalidación del acceso después de cambiar la contraseña.

Este documento resume los resultados sin datos de cuentas, credenciales ni instrucciones detalladas de reproducción. Es una revisión del código y de comprobaciones locales; no constituye una certificación de seguridad del despliegue.

## Corrección aplicada

**H-01 — Alta en producción: exposición de información sensible en errores. Corregido en el código revisado.**

La depuración queda desactivada por defecto y la clave privada de firma es obligatoria. Los errores inesperados tratados por la API devuelven `500 INTERNAL_ERROR` con un mensaje genérico. El registro de esos errores omite el mensaje original y la traza que podrían contener credenciales.

Se verificó la corrección con seis pruebas de regresión de `backend/auth_workspaces/tests/test_error_security.py`. La protección comprobada cubre errores tratados por DRF; no convierte la depuración en una opción segura para producción. El despliegue debe usar `DJANGO_DEBUG=False`, HTTPS y una clave privada propia. No se verificó un despliegue remoto de esta corrección.

Referencia: [lista de comprobación de despliegue de Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

## Mejoras pendientes

| Referencia | Prioridad | Trabajo pendiente |
| --- | --- | --- |
| H-02 | Media | Reforzar los límites de intentos con contadores compartidos y operaciones atómicas para varios procesos y solicitudes concurrentes. |
| H-03 | Media | Revisar la política de límites por cuenta para proteger el acceso legítimo sin debilitar la defensa contra intentos abusivos. |
| H-04 | Media | Acordar la política de privacidad de las respuestas de registro y la verificación de propiedad del correo; puede requerir cambios en el contrato. |
| H-05 | Media | Incorporar auditoría de accesos y rechazos con datos mínimos, acceso restringido y retención definida, excluyendo secretos. |
| H-06 | Baja | Uniformar los límites de tamaño de las entradas de autenticación y comprobar compatibilidad con las cuentas existentes. |

Estos puntos continúan pendientes. La edición de este documento no los corrige ni reduce su prioridad. Se recomienda tratar primero H-02 y H-03 y volver a comprobar los flujos afectados.

Referencias: [limitaciones de throttling de DRF](https://www.django-rest-framework.org/api-guide/throttling/), [autenticación de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) y [registro de eventos de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).

## Controles comprobados

- Generación y verificación de hashes separados para contraseña y frase, sin asignar sus valores originales a los campos de almacenamiento. La escritura se sustituyó durante estas comprobaciones locales.
- Rechazo de campos adicionales que intenten asignar permisos o estados desde el registro público.
- Respuestas de login equivalentes para correo desconocido y contraseña incorrecta.
- Rechazo de cuentas inactivas y de cuentas que requieren un segundo factor. El flujo completo de segundo factor sigue pendiente.
- Validación de firma, vencimiento y tipo de JWT; invalidación del acceso anterior tras cambiar la contraseña.
- Respuestas públicas sin contraseñas ni frases y restricciones CORS para los orígenes configurados.
- En los archivos de autenticación del frontend examinados, ausencia de registros de credenciales y conservación del token de acceso en memoria.

Referencia: [almacenamiento de contraseñas de OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## Evidencia y límites

La auditoría inicial incluyó 17 comprobaciones locales dirigidas con datos ficticios y acceso a la base de datos sustituido. Posteriormente se añadieron las seis pruebas de regresión de H-01. Estos resultados históricos no equivalen a ejecutar nuevamente toda la suite con cada cambio.

En la fecha de la auditoría, las consultas de dependencias con `pip-audit` y `npm audit` no informaron vulnerabilidades conocidas. Ese resultado debe actualizarse antes de publicar nuevas versiones y no descarta fallos desconocidos.

La auditoría no ejecutó la suite completa sobre PostgreSQL porque el archivo `database/schema.sql`, requerido por el ejecutor de pruebas, no estaba en la rama revisada. Debe obtenerse del equipo y utilizarse únicamente con una base de pruebas aislada. No se validaron los datos reales almacenados, la configuración del proveedor, los proxies ni el cifrado de las conexiones remotas.

También quedan por definir la renovación y revocación de sesiones, la política de verificación de correo y los encabezados de protección del despliegue. El contrato actual emite un token `refresh`, pero no ofrece un endpoint de renovación. Las futuras rutas deben comprobar la autorización en el backend.
