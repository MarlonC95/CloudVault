# Contrato de recuperación de contraseña de CloudVault

Describe la recuperación implementada en el backend. Complementa los contratos de [registro](propuesta-contrato-api-creacion-usuarios.md) e [inicio de sesión](contrato-api-inicio-sesion.md).

## Solicitud

`POST /api/v1/auth/recuperar-contrasena/`

Endpoint público, sin JWT. Enviar un objeto JSON con `Content-Type: application/json` y únicamente estos campos:

| Campo | Regla |
| --- | --- |
| `correo` | Correo válido, obligatorio, máximo 255 caracteres. Se quitan espacios externos y se convierte a minúsculas. |
| `palabra_secreta` | Texto obligatorio, no vacío, máximo 128 caracteres. Debe coincidir con la frase registrada. |
| `nueva_contrasena` | Texto obligatorio, de 8 a 128 caracteres. Debe cumplir los validadores del registro y ser distinto de la frase y del correo. |
| `confirmar_contrasena` | Texto obligatorio, de 8 a 128 caracteres, exactamente igual a `nueva_contrasena`. |

No se aceptan campos adicionales, valores nulos ni tipos distintos de texto. Los secretos se conservan sin recortar espacios. La frase y la nueva contraseña no pueden contener únicamente espacios. La comparación de la nueva contraseña con el correo no distingue mayúsculas.

La nueva contraseña se valida al recibirla y nuevamente contra los datos del usuario después de verificar la frase.

El ejemplo es ficticio. Los valores entre `<...>` son marcadores que deben sustituirse para una prueba; no son credenciales para reutilizar.

```json
{
  "correo": "usuario@example.invalid",
  "palabra_secreta": "<FRASE_SECRETA>",
  "nueva_contrasena": "<NUEVA_CONTRASENA>",
  "confirmar_contrasena": "<NUEVA_CONTRASENA>"
}
```

## Respuesta correcta

`200 OK`:

```json
{
  "mensaje": "Contraseña restablecida correctamente."
}
```

El restablecimiento no devuelve tokens ni inicia sesión. Después del éxito, el usuario debe iniciar sesión con la nueva contraseña.

## Errores

| HTTP | `error.code` | Condición |
| --- | --- | --- |
| `400` | `INVALID_JSON` | JSON mal formado. |
| `400` | `VALIDATION_ERROR` | Campos inválidos, faltantes o adicionales; contraseñas distintas o nueva contraseña que incumple la política. |
| `401` | `RECOVERY_VERIFICATION_FAILED` | Correo inexistente o frase incorrecta. |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | El contenido enviado no es JSON. |
| `429` | `RATE_LIMITED` | Se supera el límite de intentos. Consultar el encabezado `Retry-After`. |
| `500` | `INTERNAL_ERROR` | Error inesperado; se devuelve un mensaje genérico. |
| `503` | `SERVICE_UNAVAILABLE` | La base de datos no está disponible. |

Ambos casos de `401` devuelven el mismo cuerpo:

```json
{
  "error": {
    "code": "RECOVERY_VERIFICATION_FAILED",
    "message": "No fue posible verificar los datos proporcionados"
  }
}
```

Los errores de validación incluyen `error.fields`, según el formato del contrato de registro.

## Persistencia y seguridad

- El backend verifica la frase contra su hash almacenado y genera un nuevo hash para la contraseña. No guarda la nueva contraseña en texto plano ni modifica el hash de la frase.
- El cambio de contraseña y el evento `PASSWORD_RECOVERED` se guardan en una transacción. Un fallo en la auditoría revierte también el cambio.
- Los tokens de acceso anteriores dejan de autenticar tras el cambio. El futuro endpoint de renovación deberá comprobar también la revocación antes de emitir nuevos tokens.
- La confirmación se utiliza para validar la entrada; no se persiste. Los eventos de auditoría no incluyen secretos ni el cuerpo de la solicitud.
- Usar HTTPS fuera del desarrollo local y excluir credenciales de los registros de solicitudes y herramientas de seguimiento.
- Hay límites configurables por IP y correo. Su refuerzo para producción sigue pendiente, como indica el [resumen de seguridad](auditoria-seguridad-registro-login.md).

## Comprobación

Las pruebas están en `backend/auth_workspaces/tests/test_recovery.py`. Cubren recuperación correcta, verificación fallida, validaciones, auditoría transaccional e invalidación del acceso anterior. Deben ejecutarse con datos ficticios y una base aislada, siguiendo la [preparación del esquema](propuesta-contrato-api-creacion-usuarios.md#ejecución-y-pruebas). Este documento no certifica un despliegue.
