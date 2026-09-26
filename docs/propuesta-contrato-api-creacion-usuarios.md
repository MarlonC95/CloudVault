# Contrato de registro de usuarios de CloudVault

Describe el registro implementado en el backend. Se conserva el nombre del archivo para mantener los enlaces existentes.

## Solicitud

`POST /api/v1/auth/registro/`

Endpoint público, sin JWT. Enviar un objeto JSON con `Content-Type: application/json` y únicamente estos cuatro campos:

| Campo | Regla |
| --- | --- |
| `nombre_completo` | Texto obligatorio, de 1 a 150 caracteres después de quitar espacios externos. |
| `correo_electronico` | Correo válido, obligatorio, máximo 255 caracteres. Se quitan espacios externos y se guarda en minúsculas. |
| `contrasena` | Texto obligatorio, de 8 a 128 caracteres. Debe cumplir los validadores de contraseña de Django. |
| `palabra_secreta` | Texto obligatorio, de 12 a 128 caracteres. Debe ser distinto de la contraseña y del correo. |

La contraseña y la frase se conservan exactamente como se reciben, incluidos sus espacios; no pueden contener únicamente espacios. Se rechazan contraseñas comunes, totalmente numéricas o demasiado similares a los datos del usuario. La comparación de la frase con el correo no distingue mayúsculas.

No se aceptan valores nulos, tipos distintos de texto ni campos adicionales. La confirmación de contraseña pertenece al formulario y no se envía en este endpoint. Tampoco se aceptan roles, planes, organizaciones, estados de cuenta ni hashes proporcionados por el cliente.

Los ejemplos de este documento son ficticios. Los valores entre `<...>` son marcadores que deben sustituirse al probar la API, no credenciales para reutilizar.

```json
{
  "nombre_completo": "Usuario de ejemplo",
  "correo_electronico": "usuario@example.invalid",
  "contrasena": "<CONTRASENA>",
  "palabra_secreta": "<FRASE_SECRETA>"
}
```

## Respuesta correcta

`201 Created`:

```json
{
  "data": {
    "id": "00000000-0000-4000-8000-000000000001",
    "nombre_completo": "Usuario de ejemplo",
    "correo_electronico": "usuario@example.invalid",
    "esta_activo": true,
    "fecha_creacion": "2026-01-01T00:00:00Z"
  }
}
```

La API asigna el identificador, la fecha y el estado. Esta respuesta confirma la creación de la cuenta; no verifica la propiedad del correo, no asigna una organización ni un plan y no inicia sesión. Para obtener tokens se utiliza el [inicio de sesión](contrato-api-inicio-sesion.md).

## Errores

| HTTP | `error.code` | Condición |
| --- | --- | --- |
| `400` | `INVALID_JSON` | JSON mal formado. |
| `400` | `VALIDATION_ERROR` | Campos ausentes, vacíos, adicionales, con tipo incorrecto o que incumplen las reglas. |
| `409` | `CORREO_EN_USO` | Ya existe una cuenta con ese correo. |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | El contenido enviado no es JSON. |
| `429` | `RATE_LIMITED` | Se supera el límite de intentos. Consultar el encabezado `Retry-After`. |
| `500` | `INTERNAL_ERROR` | Error inesperado; se devuelve un mensaje genérico. |
| `503` | `SERVICE_UNAVAILABLE` | La base de datos no está disponible. |

Formato de validación:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Revisa los datos enviados.",
    "fields": {
      "palabra_secreta": ["Debe ser distinta de la contraseña y el correo."]
    }
  }
}
```

`fields` aparece en errores de validación; `non_field_errors` identifica errores del objeto completo. El cliente debe usar `error.code` para decidir cómo tratar el error.

## Persistencia y seguridad

- El backend genera hashes separados para la contraseña y la frase mediante las utilidades de Django. Los valores originales no se guardan en sus columnas ni se devuelven en la respuesta.
- La cuenta y el evento `USER_REGISTERED` se guardan en una misma transacción. Si falla la escritura del evento, también se revierte la creación de la cuenta.
- El correo se comprueba sin distinguir mayúsculas y la restricción de unicidad de PostgreSQL protege las altas concurrentes del mismo correo normalizado. Otros procesos que escriban usuarios deben respetar esa normalización.
- El evento de auditoría no incluye contraseñas, frases ni el cuerpo de la solicitud. Los sistemas externos de registros y seguimiento de errores deben excluir también esos datos.
- Las credenciales se envían al servidor mediante HTTPS fuera del desarrollo local. El hash se genera en el backend antes de persistirlo; no sustituye el cifrado del transporte.
- Hay límites configurables de intentos por IP y correo. Su refuerzo para producción sigue pendiente, como indica el [resumen de seguridad](auditoria-seguridad-registro-login.md).

El registro no ofrece idempotencia por clave. Si se pierde una respuesta exitosa y se repite el alta, el mismo correo devuelve `409`. La respuesta de correo duplicado forma parte del contrato actual y su política de privacidad sigue pendiente de revisión.

## Ejecución y pruebas

Consulta el [README del backend](../backend/README.md) para preparar el entorno. Las tablas de usuarios y auditoría se administran mediante el esquema SQL del proyecto; `migrate` no las crea a partir de estos modelos.

Las pruebas están en `backend/auth_workspaces/tests/`. Para ejecutar las pruebas con PostgreSQL se necesita una base aislada, un `DB_TEST_NAME` distinto de la base de la aplicación y el archivo `database/schema.sql` mantenido por el equipo. Este último no está incluido en la rama revisada.

Los casos a verificar incluyen registro válido, duplicados, rechazo de campos adicionales, almacenamiento de ambos hashes, reversión ante fallos de auditoría y respuestas sin secretos. Este documento describe el contrato; no certifica un despliegue.
