# Contrato de inicio de sesión de CloudVault

Describe el inicio de sesión implementado en el backend. Complementa los contratos de [registro](propuesta-contrato-api-creacion-usuarios.md) y [recuperación de contraseña](contrato-api-recuperacion-contrasena.md).

## Solicitud

`POST /api/v1/auth/login/`

Endpoint público, sin JWT. Enviar un objeto JSON con `Content-Type: application/json` y únicamente estos campos:

| Campo | Regla |
| --- | --- |
| `correo` | Correo válido, obligatorio, máximo 255 caracteres. Se quitan espacios externos y se convierte a minúsculas. |
| `contrasena` | Texto obligatorio, no vacío. Se verifica sin recortar espacios ni alterar sus caracteres. |

No se aceptan valores nulos, tipos distintos de texto ni campos adicionales. Este endpoint recibe `correo`; el de registro utiliza `correo_electronico`.

Los ejemplos son ficticios. Los valores entre `<...>` son marcadores, no credenciales ni tokens utilizables.

```json
{
  "correo": "usuario@example.invalid",
  "contrasena": "<CONTRASENA>"
}
```

## Respuesta correcta

`200 OK`:

```json
{
  "data": {
    "usuario": {
      "id": "00000000-0000-4000-8000-000000000001",
      "nombre_completo": "Usuario de ejemplo",
      "correo_electronico": "usuario@example.invalid",
      "esta_activo": true,
      "fecha_creacion": "2026-01-01T00:00:00Z"
    },
    "tokens": {
      "access": "<JWT_DE_ACCESO>",
      "refresh": "<JWT_DE_RENOVACION>"
    }
  }
}
```

El token `access` tiene una duración configurada de 15 minutos y el `refresh`, de un día. Para las rutas protegidas se envía `Authorization: Bearer <access>`.

Actualmente se emite `refresh`, pero todavía no existe un endpoint para renovarlo. El cliente no debe asumir que hay renovación automática. Un cambio de contraseña invalida los tokens de acceso anteriores en la autenticación del backend.

## Errores

| HTTP | `error.code` | Condición |
| --- | --- | --- |
| `400` | `INVALID_JSON` | JSON mal formado. |
| `400` | `VALIDATION_ERROR` | Campos ausentes, vacíos, adicionales o con tipo o formato incorrecto. |
| `401` | `INVALID_CREDENTIALS` | Credenciales incorrectas o cuenta no habilitada para este flujo. |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | El contenido enviado no es JSON. |
| `429` | `RATE_LIMITED` | Se supera el límite de intentos. Consultar el encabezado `Retry-After`. |
| `500` | `INTERNAL_ERROR` | Error inesperado; se devuelve un mensaje genérico. |
| `503` | `SERVICE_UNAVAILABLE` | La base de datos no está disponible. |

El correo desconocido y la contraseña incorrecta producen el mismo cuerpo:

```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Correo o contraseña incorrectos"
  }
}
```

Las cuentas inactivas y las que requieren un segundo factor también reciben ese `401`. El flujo completo de segundo factor aún no está implementado. Los errores de validación incluyen `error.fields`, según el formato del contrato de registro.

## Seguridad y comprobación

La contraseña se verifica contra su hash mediante las utilidades de Django. La frase de recuperación no interviene en el login. No se devuelve la contraseña ni su hash de almacenamiento en los campos públicos del usuario.

Usar HTTPS fuera del desarrollo local. Las contraseñas, frases, claves de firma y tokens reales deben quedar fuera de documentos, repositorios y registros de solicitudes. Hay límites configurables por IP y correo; las mejoras pendientes constan en el [resumen de seguridad](auditoria-seguridad-registro-login.md).

Las pruebas de este flujo están en `backend/auth_workspaces/tests/test_login.py`. Deben ejecutarse con datos ficticios y una base aislada. La preparación del esquema se explica en el [contrato de registro](propuesta-contrato-api-creacion-usuarios.md#ejecución-y-pruebas). Este documento no certifica la configuración de un despliegue.
