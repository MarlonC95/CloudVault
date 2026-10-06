# Contratos de API — CloudVault

Este documento define los contratos de API (JSON) para el dashboard, la carga y
descarga de archivos, la personalización de usuario, la revisión de Mi Unidad y
el módulo de planes.

Está pensado para que Frontend y Backend trabajen contra el mismo contrato. Los
endpoints marcados como **✅ Implementado** ya existen en el backend; los
marcados como **🆕 Pendiente** deben implementarse respetando este formato.

> Base URL de desarrollo: `http://127.0.0.1:8000`
> Prefijo de versión: `/api/v1/` (ya usado por la app `accounts`).

---

## 0. Convenciones generales

### 0.1 Encabezados

| Encabezado | Cuándo se usa | Valor |
| --- | --- | --- |
| `Content-Type` | En toda petición con cuerpo JSON | `application/json` |
| `Authorization` | En todo endpoint protegido | `Bearer <access_token>` |

### 0.2 Formato de éxito

Todas las respuestas exitosas **nuevas** se envuelven en `data`. Esta convención
ya la usa `login` y `registro`:

```json
{ "data": { "...": "..." } }
```

**Excepción existente:** `POST /api/v1/auth/recuperar-contrasena/` responde con
`{"mensaje": "..."}` (sin `data`). Este contrato **no se modifica** porque fue
definido por otro miembro del equipo; se documenta tal cual está implementado.

### 0.3 Formato de error

Formato uniforme, ya implementado por el helper `error()` en
`backend/accounts/views.py`:

```json
{
  "error": {
    "code": "CODIGO_DE_ERROR",
    "fields": {
      "campo": ["Mensaje de validación."]
    }
  }
}
```

- `fields` solo aparece cuando el error es de validación de campos.
- El Frontend ya lee `error.response.data.error.code` (ver
  `frontend/src/services/authService.ts`), por lo que este formato es obligatorio
  en todos los módulos nuevos.

### 0.4 Tabla de códigos de error

| HTTP | `code` | Cuándo |
| --- | --- | --- |
| 400 | `VALIDATION_ERROR` | Campos inválidos o faltantes (`fields` incluido) |
| 400 | `INVALID_CREDENTIALS` | Credenciales incorrectas en login |
| 400 | `RECOVERY_VERIFICATION_FAILED` | La frase secreta no coincide |
| 401 | `NO_AUTENTICADO` | Falta el encabezado `Authorization` |
| 401 | `TOKEN_INVALIDO` | Token expirado, malformado o revocado |
| 403 | `SIN_PERMISO` | El usuario no es dueño del recurso |
| 404 | `NO_ENCONTRADO` | El recurso no existe |
| 409 | `CORREO_EN_USO` | El correo ya está registrado |
| 409 | `CUOTA_EXCEDIDA` | No hay almacenamiento disponible |
| 429 | `RATE_LIMITED` | Demasiados intentos |
| 500 | `ERROR_INTERNO` | Error no controlado del servidor |
| 503 | `SERVICE_UNAVAILABLE` | Servicio temporalmente no disponible |

> El Frontend ya contempla `RATE_LIMITED` y `SERVICE_UNAVAILABLE`
> (`authService.ts`), aunque el backend todavía no los emita.

### 0.5 Paginación

Los listados van envueltos para no romper la convención de `data`:

```json
{
  "data": {
    "count": 42,
    "next": "http://127.0.0.1:8000/api/v1/archivos/?page=2",
    "previous": null,
    "results": []
  }
}
```

### 0.6 Fechas y tamaños

- Fechas: ISO 8601 en UTC, p. ej. `"2026-10-04T18:30:00Z"`. El Frontend se
  encarga de formatearlas a texto relativo ("Hace 2 horas").
- Tamaños: se exponen en **bytes** (entero) en `tamano_bytes` y un texto
  formateado en `tamano_legible` (p. ej. `"4.2 MB"`).

---

## 1. Autenticación

### 1.1 `POST /api/v1/auth/registro/` — ✅ Implementado

Sin autenticación.

**Body**

```json
{
  "nombre_completo": "Mily Santay",
  "correo_electronico": "mily@cloudvault.io",
  "contrasena": "MiClaveSegura123",
  "palabra_secreta": "mi frase secreta de recuperacion"
}
```

**201 Created**

```json
{
  "data": {
    "id": "1",
    "nombre_completo": "Mily Santay",
    "correo_electronico": "mily@cloudvault.io"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "correo_electronico": ["Ingresa un correo electrónico válido."],
      "contrasena": ["La contraseña debe tener entre 8 y 128 caracteres."]
    }
  }
}
```

**409** `CORREO_EN_USO`

```json
{ "error": { "code": "CORREO_EN_USO" } }
```

### 1.2 `POST /api/v1/auth/login/` — ✅ Implementado

Sin autenticación.

**Body**

```json
{
  "correo": "mily@cloudvault.io",
  "contrasena": "MiClaveSegura123"
}
```

**200 OK**

```json
{
  "data": {
    "usuario": {
      "id": "1",
      "nombre_completo": "Mily Santay",
      "correo_electronico": "mily@cloudvault.io"
    },
    "tokens": {
      "access": "eyJhbGciOi...",
      "refresh": "eyJhbGciOi..."
    }
  }
}
```

**400** `VALIDATION_ERROR` / **401** `INVALID_CREDENTIALS`

```json
{ "error": { "code": "INVALID_CREDENTIALS" } }
```

### 1.3 `POST /api/v1/auth/recuperar-contrasena/` — ✅ Implementado

Sin autenticación. **Nota:** este endpoint responde con `{"mensaje": ...}` por
tratarse de una acción tipo comando ya definida por el equipo. No modificar.

**Body**

```json
{
  "correo": "mily@cloudvault.io",
  "palabra_secreta": "mi frase secreta de recuperacion",
  "nueva_contrasena": "NuevaClave456",
  "confirmar_contrasena": "NuevaClave456"
}
```

**200 OK**

```json
{ "mensaje": "La contraseña se actualizó correctamente." }
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "confirmar_contrasena": ["Las contraseñas no coinciden."]
    }
  }
}
```

**400** `RECOVERY_VERIFICATION_FAILED`

```json
{ "error": { "code": "RECOVERY_VERIFICATION_FAILED" } }
```

### 1.4 `POST /api/v1/auth/refresh/` — 🆕 Pendiente

Renueva el access token usando el refresh token. Necesario porque el access
token expira en 15 minutos (`SIMPLE_JWT.ACCESS_TOKEN_LIFETIME`).

Sin autenticación (solo requiere el refresh en el body).

**Body**

```json
{ "refresh": "eyJhbGciOi..." }
```

**200 OK**

```json
{
  "data": {
    "access": "eyJhbGciOi...",
    "refresh": "eyJhbGciOi..."
  }
}
```

**401** `TOKEN_INVALIDO`

```json
{ "error": { "code": "TOKEN_INVALIDO" } }
```

### 1.5 `POST /api/v1/auth/logout/` — 🆕 Pendiente

Invalida el refresh token (requiere blacklist de SimpleJWT).

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{ "refresh": "eyJhbGciOi..." }
```

**200 OK**

```json
{ "data": { "mensaje": "Sesión cerrada correctamente." } }
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

---

## 2. Personalización de usuario (Perfil)

Respalda `frontend/src/pages/ProfilePage.tsx`.

### 2.1 `GET /api/v1/auth/perfil/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "id": "1",
    "nombre_completo": "Mily Santay",
    "correo_electronico": "mily@cloudvault.io",
    "rol": "admin",
    "plan": {
      "id": "pro",
      "nombre": "Pro PaaS"
    },
    "dos_factores": true,
    "almacenamiento": {
      "usado_bytes": 48318382080,
      "cuota_bytes": 107374182400,
      "usado_legible": "45 GB",
      "cuota_legible": "100 GB",
      "porcentaje_usado": 45
    },
    "fecha_registro": "2026-01-15T10:00:00Z"
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 2.2 `PATCH /api/v1/auth/perfil/` — 🆕 Pendiente

Actualiza datos editables. Resuelve el `TODO(backend)` de
`ProfilePage.tsx` (`PATCH /api/auth/perfil/`).

**Headers:** `Authorization: Bearer <access>`

**Body** (todos los campos opcionales; enviar solo lo que cambia)

```json
{
  "nombre_completo": "Mily Santay",
  "correo_electronico": "mily.nuevo@cloudvault.io"
}
```

**200 OK**

```json
{
  "data": {
    "id": "1",
    "nombre_completo": "Mily Santay",
    "correo_electronico": "mily.nuevo@cloudvault.io"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "correo_electronico": ["Ingresa un correo electrónico válido."]
    }
  }
}
```

**409** `CORREO_EN_USO`

```json
{ "error": { "code": "CORREO_EN_USO" } }
```

### 2.3 `POST /api/v1/auth/cambiar-contrasena/` — 🆕 Pendiente

Respalda la tarjeta "Cambiar Contraseña" de `ProfilePage.tsx`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "contrasena_actual": "MiClaveSegura123",
  "nueva_contrasena": "NuevaClave456",
  "confirmar_contrasena": "NuevaClave456"
}
```

**200 OK**

```json
{ "data": { "mensaje": "La contraseña se actualizó correctamente." } }
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "contrasena_actual": ["La contraseña actual no es correcta."],
      "confirmar_contrasena": ["Las contraseñas no coinciden."]
    }
  }
}
```

### 2.4 `POST /api/v1/auth/cambiar-palabra-secreta/` — 🆕 Pendiente

Respalda "Modificar Palabra Secreta" de `ProfilePage.tsx`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "contrasena_actual": "NuevaClave456",
  "nueva_palabra_secreta": "otra frase secreta personal"
}
```

**200 OK**

```json
{ "data": { "mensaje": "La palabra secreta se actualizó correctamente." } }
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "nueva_palabra_secreta": ["La frase debe tener entre 12 y 128 caracteres."]
    }
  }
}
```

### 2.5 `GET /api/v1/auth/preferencias/` — 🆕 Pendiente

Preferencias del usuario (por ahora, 2FA). Respalda el toggle de 2FA.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "dos_factores": true,
    "idioma": "es",
    "zona_horaria": "America/Guatemala"
  }
}
```

### 2.6 `PATCH /api/v1/auth/preferencias/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{ "dos_factores": false }
```

**200 OK**

```json
{ "data": { "dos_factores": false } }
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "dos_factores": ["Se esperaba un valor booleano."]
    }
  }
}
```

---

## 3. Mi Unidad (Dashboard)

Respalda `frontend/src/pages/DashboardPage.tsx` y los componentes
`TarjetaCarpeta`, `ModalNuevaCarpeta`, `TablaArchivos`.

### 3.1 `GET /api/v1/carpetas/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**Query params opcionales**

| Param | Tipo | Descripción |
| --- | --- | --- |
| `page` | int | Número de página (paginación) |

**200 OK**

```json
{
  "data": {
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "documentos",
        "nombre": "Documentos",
        "color": "#2563EB",
        "color_fondo": "#EFF6FF",
        "cantidad_archivos": 2,
        "creado_en": "2026-08-01T10:00:00Z"
      },
      {
        "id": "proyectos",
        "nombre": "Proyectos",
        "color": "#7C3AED",
        "color_fondo": "#F5F3FF",
        "cantidad_archivos": 2,
        "creado_en": "2026-08-02T10:00:00Z"
      }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 3.2 `POST /api/v1/carpetas/` — 🆕 Pendiente

Resuelve el `TODO(backend)` de `DashboardPage.tsx:94`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "nombre": "Contratos 2026",
  "color": "#2563EB",
  "color_fondo": "#EFF6FF"
}
```

`color` y `color_fondo` son opcionales; si no se envían, el backend asigna una
paleta por defecto (equivalent al arreglo `COLORES_CARPETA_NUEVA` del Frontend).

**201 Created**

```json
{
  "data": {
    "id": "carpeta-1700000000000",
    "nombre": "Contratos 2026",
    "color": "#2563EB",
    "color_fondo": "#EFF6FF",
    "cantidad_archivos": 0,
    "creado_en": "2026-10-04T18:30:00Z"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "nombre": ["El nombre de la carpeta es obligatorio."]
    }
  }
}
```

**409** `VALIDATION_ERROR` (nombre duplicado)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "nombre": ["Ya existe una carpeta con ese nombre."]
    }
  }
}
```

### 3.3 `GET /api/v1/carpetas/{id}/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**200 OK** — mismo objeto que en el listado.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.4 `PATCH /api/v1/carpetas/{id}/` — 🆕 Pendiente

Renombrar / recolorear.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{ "nombre": "Contratos 2026 (cerrados)" }
```

**200 OK**

```json
{
  "data": {
    "id": "carpeta-1700000000000",
    "nombre": "Contratos 2026 (cerrados)",
    "color": "#2563EB",
    "color_fondo": "#EFF6FF",
    "cantidad_archivos": 0,
    "creado_en": "2026-10-04T18:30:00Z"
  }
}
```

**404** `NO_ENCONTRADO` / **403** `SIN_PERMISO`

```json
{ "error": { "code": "SIN_PERMISO" } }
```

### 3.5 `DELETE /api/v1/carpetas/{id}/` — 🆕 Pendiente

Elimina la carpeta. Los archivos dentro se mueven a "Sin carpeta" (o a la
papelera, según se defina con el equipo).

**Headers:** `Authorization: Bearer <access>`

**204 No Content** — sin cuerpo.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.6 `GET /api/v1/archivos/` — 🆕 Pendiente

Listado con filtros que respaldan `BuscadorArchivos.tsx`.

**Headers:** `Authorization: Bearer <access>`

**Query params**

| Param | Valores | Descripción |
| --- | --- | --- |
| `carpeta` | id | Filtra por carpeta (`null`/ausente = todos) |
| `busqueda` | texto | Coincidencia por nombre |
| `tipo` | `pdf`,`zip`,`png`,`js`,`xlsx`,`mp4`,`docx`,`otro` | Filtro por tipo |
| `fecha` | `recientes`,`este-mes`,`anteriores` | Rango de fecha |
| `tamano` | `pequeno`,`mediano`,`grande` | Rango de tamaño (`<1MB`, `1-100MB`, `>100MB`) |
| `page` | int | Paginación |

**200 OK**

```json
{
  "data": {
    "count": 6,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "1",
        "nombre": "Arquitectura_PaaS_v1.pdf",
        "tipo": "pdf",
        "tamano_bytes": 4404019,
        "tamano_legible": "4.2 MB",
        "fecha_modificacion": "2026-10-04T16:30:00Z",
        "propietario": { "id": "1", "nombre_completo": "Mily Santay" },
        "cifrado": true,
        "es_nuevo": true,
        "en_papelera": false,
        "carpeta_id": "documentos"
      }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 3.7 `GET /api/v1/archivos/{id}/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**200 OK** — mismo objeto que en el listado.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.8 `PATCH /api/v1/archivos/{id}/` — 🆕 Pendiente

Renombrar.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{ "nombre": "Arquitectura_PaaS_v2.pdf" }
```

**200 OK**

```json
{
  "data": {
    "id": "1",
    "nombre": "Arquitectura_PaaS_v2.pdf",
    "tipo": "pdf",
    "tamano_bytes": 4404019,
    "tamano_legible": "4.2 MB",
    "fecha_modificacion": "2026-10-04T18:30:00Z",
    "propietario": { "id": "1", "nombre_completo": "Mily Santay" },
    "cifrado": true,
    "es_nuevo": false,
    "en_papelera": false,
    "carpeta_id": "documentos"
  }
}
```

**403** `SIN_PERMISO` / **404** `NO_ENCONTRADO`

```json
{ "error": { "code": "SIN_PERMISO" } }
```

### 3.9 `DELETE /api/v1/archivos/{id}/` — 🆕 Pendiente

Envío a la papelera lógica (retención 30 días). No borra el objeto del storage.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{ "data": { "mensaje": "El archivo se movió a la papelera." } }
```

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.10 `POST /api/v1/archivos/{id}/mover/` — 🆕 Pendiente

Respalda `ModalMoverArchivo.tsx`.

**Headers:** `Authorization: Bearer <access>`

**Body** (`carpeta_id: null` = "Sin carpeta")

```json
{ "carpeta_id": "proyectos" }
```

**200 OK**

```json
{
  "data": {
    "id": "1",
    "nombre": "Arquitectura_PaaS_v1.pdf",
    "carpeta_id": "proyectos",
    "fecha_modificacion": "2026-10-04T18:30:00Z"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "carpeta_id": ["La carpeta indicada no existe."]
    }
  }
}
```

### 3.11 `GET /api/v1/unidad/resumen/` — 🆕 Pendiente

Resumen de almacenamiento. Respalda el bloque lateral de
`DashboardLayout.tsx`, `ProfilePage.tsx` y `PlanesPage.tsx`.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "usado_bytes": 48318382080,
    "cuota_bytes": 107374182400,
    "usado_legible": "45 GB",
    "cuota_legible": "100 GB",
    "libre_legible": "55 GB",
    "porcentaje_usado": 45,
    "cantidad_archivos": 6,
    "cantidad_carpetas": 3,
    "por_categoria": [
      { "etiqueta": "Documentos", "tamano_legible": "18 GB", "color": "#2563EB" },
      { "etiqueta": "Backups", "tamano_legible": "21 GB", "color": "#7C3AED" },
      { "etiqueta": "Otros", "tamano_legible": "6 GB", "color": "#0891B2" }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

---

## 4. Carga de archivos (URLs prefirmadas S3/MinIO)

Respalda `ModalSubirArchivo.tsx` y `NotificacionCargas.tsx`. El flujo es en dos
pasos: el backend firma la URL de subida y el Frontend sube el binario
directamente al storage.

### 4.1 `POST /api/v1/archivos/iniciar-carga/` — 🆕 Pendiente

Resuelve el `TODO(backend)` de `DashboardPage.tsx:100`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "nombre": "Especificaciones_PaaS.pdf",
  "tamano_bytes": 3250585,
  "tipo_mime": "application/pdf",
  "carpeta_id": "documentos"
}
```

`carpeta_id` puede ser `null`.

**201 Created**

```json
{
  "data": {
    "archivo_id": "subido-1700000000001",
    "url_subida": "https://minio.local/cloudvault/...&X-Amz-Signature=...",
    "metodo": "PUT",
    "encabezados": {
      "Content-Type": "application/pdf"
    },
    "expira_en": "2026-10-04T18:45:00Z"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "nombre": ["El nombre del archivo es obligatorio."],
      "tamano_bytes": ["El archivo supera el tamaño máximo permitido."]
    }
  }
}
```

**409** `CUOTA_EXCEDIDA`

```json
{
  "error": {
    "code": "CUOTA_EXCEDIDA",
    "fields": {
      "tamano_bytes": ["No tienes almacenamiento suficiente disponible."]
    }
  }
}
```

### 4.2 `POST /api/v1/archivos/{id}/confirmar-carga/` — 🆕 Pendiente

Se llama cuando el Frontend terminó de subir el binario a `url_subida`. Activa el
archivo en la base de datos.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{ "etag": "\"9c3b8f...\"`" }
```

`etag` es opcional (devuelto por el storage).

**200 OK**

```json
{
  "data": {
    "id": "subido-1700000000001",
    "nombre": "Especificaciones_PaaS.pdf",
    "tipo": "pdf",
    "tamano_bytes": 3250585,
    "tamano_legible": "3.1 MB",
    "fecha_modificacion": "2026-10-04T18:30:00Z",
    "propietario": { "id": "1", "nombre_completo": "Mily Santay" },
    "cifrado": false,
    "es_nuevo": true,
    "en_papelera": false,
    "carpeta_id": "documentos"
  }
}
```

**404** `NO_ENCONTRADO` (si la carga no se inició o el objeto no existe)

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 4.3 `GET /api/v1/archivos/{id}/estado-carga/` — 🆕 Pendiente

Opcional, para refrescar progreso/cola en `NotificacionCargas.tsx`.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "archivo_id": "subido-1700000000001",
    "estado": "subiendo",
    "progreso": 85
  }
}
```

`estado` ∈ `en-cola`, `subiendo`, `completado`, `error`.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

---

## 5. Descarga de archivos

Respalda `DashboardPage.tsx:61` y el botón "Descargar" del
`PanelDetalleArchivo.tsx`.

### 5.1 `GET /api/v1/archivos/{id}/descarga/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "url_descarga": "https://minio.local/cloudvault/...&X-Amz-Signature=...",
    "nombre": "Arquitectura_PaaS_v1.pdf",
    "expira_en": "2026-10-04T18:40:00Z"
  }
}
```

**403** `SIN_PERMISO` / **404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 5.2 `GET /api/v1/archivos/{id}/vista-previa/` — 🆕 Pendiente

URL temporal para previsualizar (imágenes, PDF). Respalda "Vista previa" del
menú de `TablaArchivos.tsx`.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "url_vista_previa": "https://minio.local/cloudvault/...&X-Amz-Signature=...",
    "tipo": "pdf",
    "expira_en": "2026-10-04T18:35:00Z"
  }
}
```

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

---

## 6. Compartir archivos (enlaces públicos)

Respalda `ModalCompartir.tsx` (`TODO` en línea 16, `POST /api/enlaces-publicos/`).

### 6.1 `POST /api/v1/enlaces-compartidos/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "archivo_id": "1",
  "expira_en": "2026-10-11T18:30:00Z",
  "password": null,
  "permite_descarga": true
}
```

`expira_en` y `password` son opcionales (por defecto 7 días, sin contraseña).

**201 Created**

```json
{
  "data": {
    "id": "enlace-1700000000002",
    "archivo_id": "1",
    "url_compartida": "https://cloudvault.app/compartido/ab12cd34ef56",
    "token": "ab12cd34ef56",
    "expira_en": "2026-10-11T18:30:00Z",
    "password_protegido": false,
    "permite_descarga": true,
    "creado_en": "2026-10-04T18:30:00Z"
  }
}
```

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 6.2 `GET /api/v1/enlaces-compartidos/` — 🆕 Pendiente

Listado de enlaces creados por el usuario.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "enlace-1700000000002",
        "archivo_id": "1",
        "nombre_archivo": "Arquitectura_PaaS_v1.pdf",
        "url_compartida": "https://cloudvault.app/compartido/ab12cd34ef56",
        "expira_en": "2026-10-11T18:30:00Z",
        "password_protegido": false,
        "activo": true,
        "creado_en": "2026-10-04T18:30:00Z"
      }
    ]
  }
}
```

### 6.3 `DELETE /api/v1/enlaces-compartidos/{id}/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**204 No Content** — sin cuerpo.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 6.4 `GET /api/v1/publico/{token}/` — 🆕 Pendiente (sin auth)

Acceso a un archivo compartido. No requiere `Authorization`.

**Query param opcional:** `password` (si el enlace está protegido).

**200 OK**

```json
{
  "data": {
    "nombre": "Arquitectura_PaaS_v1.pdf",
    "tipo": "pdf",
    "tamano_legible": "4.2 MB",
    "url_descarga": "https://minio.local/cloudvault/...&X-Amz-Signature=...",
    "permite_descarga": true,
    "expira_en": "2026-10-11T18:30:00Z"
  }
}
```

**404** `NO_ENCONTRADO` (token inválido o expirado) / **403** `SIN_PERMISO`
(contraseña incorrecta)

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

---

## 7. Revisión de Mi Unidad / Almacenamiento

### 7.1 `GET /api/v1/unidad/resumen/` — 🆕 Pendiente

Ver sección **3.11**.

### 7.2 `GET /api/v1/unidad/actividad/` — 🆕 Pendiente

Respalda "Actividad reciente" de `ProfilePage.tsx:27`.

**Headers:** `Authorization: Bearer <access>`

**Query params:** `page` (opcional).

**200 OK**

```json
{
  "data": {
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "act-1",
        "accion": "archivo_subido",
        "descripcion": "Archivo subido",
        "archivo": "Arquitectura_PaaS_v1.pdf",
        "creado_en": "2026-10-04T16:30:00Z"
      },
      {
        "id": "act-2",
        "accion": "compartido",
        "descripcion": "Compartido con equipo",
        "archivo": "Proyectos_2026",
        "creado_en": "2026-10-03T09:00:00Z"
      },
      {
        "id": "act-3",
        "accion": "descarga",
        "descripcion": "Descarga",
        "archivo": "Respaldo_BaseDatos.zip",
        "creado_en": "2026-08-30T12:00:00Z"
      }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 7.3 `GET /api/v1/recientes/` — 🆕 Pendiente

Módulo "Recientes" del menú (`DashboardLayout.tsx`).

**Headers:** `Authorization: Bearer <access>`

**Query params:** `page`, `limite` (opcional).

**200 OK**

```json
{
  "data": {
    "count": 6,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "1",
        "nombre": "Arquitectura_PaaS_v1.pdf",
        "tipo": "pdf",
        "tamano_legible": "4.2 MB",
        "fecha_modificacion": "2026-10-04T16:30:00Z",
        "carpeta_id": "documentos"
      }
    ]
  }
}
```

---

## 8. Papelera

Retención de 30 días (según README). El borrado definitivo elimina el objeto del
storage.

### 8.1 `GET /api/v1/papelera/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**Query params:** `page`.

**200 OK**

```json
{
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "2",
        "nombre": "Respaldo_BaseDatos.zip",
        "tipo": "zip",
        "tamano_legible": "128 MB",
        "eliminado_en": "2026-10-01T10:00:00Z",
        "expira_en": "2026-10-31T10:00:00Z",
        "dias_restantes": 27,
        "carpeta_id": null
      }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 8.2 `POST /api/v1/papelera/{id}/restaurar/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{ "data": { "mensaje": "El archivo se restauró correctamente." } }
```

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 8.3 `DELETE /api/v1/papelera/{id}/` — 🆕 Pendiente

Borrado definitivo (elimina también el objeto del storage).

**Headers:** `Authorization: Bearer <access>`

**204 No Content** — sin cuerpo.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

---

## 9. Compartidos conmigo

Módulo "Compartidos conmigo" del menú (`DashboardLayout.tsx`).

### 9.1 `GET /api/v1/compartidos-conmigo/` — 🆕 Pendiente

**Headers:** `Authorization: Bearer <access>`

**Query params:** `page`, `busqueda`, `tipo`.

**200 OK**

```json
{
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "share-1",
        "archivo_id": "10",
        "nombre": "Presupuesto_Q4.xlsx",
        "tipo": "xlsx",
        "tamano_legible": "840 KB",
        "propietario": { "id": "2", "nombre_completo": "Carlos Ruiz" },
        "permiso": "lectura",
        "fecha_modificacion": "2026-10-02T14:00:00Z",
        "carpeta_id": null
      }
    ]
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

---

## 10. Módulo de Planes

Respalda `frontend/src/pages/PlanesPage.tsx`.

### 10.1 `GET /api/v1/planes/` — 🆕 Pendiente

Catálogo de planes. Puede ser público o requerir auth; se recomienda requerir
`Authorization` para poder marcar el plan actual.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "gratuito",
        "nombre": "Gratuito",
        "precio_mensual": 0,
        "precio_anual": 0,
        "almacenamiento_bytes": 16106127360,
        "almacenamiento_legible": "15 GB",
        "es_popular": false,
        "caracteristicas": [
          "15 GB almacenamiento",
          "1 Usuario",
          "Cifrado estándar",
          "Soporte por comunidad"
        ]
      },
      {
        "id": "pro",
        "nombre": "Pro PaaS",
        "precio_mensual": 29,
        "precio_anual": 278,
        "almacenamiento_bytes": 107374182400,
        "almacenamiento_legible": "100 GB",
        "es_popular": true,
        "caracteristicas": [
          "100 GB almacenamiento",
          "Hasta 5 Usuarios",
          "Cifrado de extremo a extremo",
          "Versionado de archivos",
          "Soporte 24/7"
        ]
      },
      {
        "id": "empresarial",
        "nombre": "Empresarial",
        "precio_mensual": 99,
        "precio_anual": 950,
        "almacenamiento_bytes": null,
        "almacenamiento_legible": "Ilimitado",
        "es_popular": false,
        "caracteristicas": [
          "Almacenamiento ilimitado",
          "Usuarios ilimitados",
          "Logs de auditoría avanzada",
          "API dedicada",
          "SLA del 99.9%"
        ]
      }
    ]
  }
}
```

> `precio_anual` refleja el descuento del 20% (`-20%` mostrado en la UI).

### 10.2 `GET /api/v1/mi-plan/` — 🆕 Pendiente

Plan actual del usuario y consumo. Alimenta la barra de `PlanesPage.tsx` y el
bloque lateral del dashboard.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "plan": {
      "id": "pro",
      "nombre": "Pro PaaS",
      "precio_mensual": 29,
      "tipo_facturacion": "mensual"
    },
    "estado": "activo",
    "renueva_en": "2026-11-04T10:00:00Z",
    "almacenamiento": {
      "usado_bytes": 48318382080,
      "cuota_bytes": 107374182400,
      "usado_legible": "45 GB",
      "cuota_legible": "100 GB",
      "libre_legible": "55 GB",
      "porcentaje_usado": 45
    }
  }
}
```

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 10.3 `POST /api/v1/mi-plan/suscribir/` — 🆕 Pendiente

Cambia o contrata un plan. Resuelve el `TODO(backend)` del botón
"Actualizar Plan" de `PlanesPage.tsx` (pago simulado por ahora).

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "plan_id": "empresarial",
  "tipo_facturacion": "anual"
}
```

**200 OK**

```json
{
  "data": {
    "plan": {
      "id": "empresarial",
      "nombre": "Empresarial",
      "tipo_facturacion": "anual"
    },
    "estado": "activo",
    "renueva_en": "2027-10-04T10:00:00Z"
  }
}
```

**400** `VALIDATION_ERROR`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "plan_id": ["El plan indicado no existe."],
      "tipo_facturacion": ["El tipo de facturación debe ser 'mensual' o 'anual'."]
    }
  }
}
```

**409** `CUOTA_EXCEDIDA` (al bajar de plan con más uso que la nueva cuota)

```json
{
  "error": {
    "code": "CUOTA_EXCEDIDA",
    "fields": {
      "plan_id": ["Tu uso actual supera la cuota del nuevo plan."]
    }
  }
}
```

### 10.4 `GET /api/v1/mi-plan/facturas/` — 🆕 Pendiente

Historial de facturación.

**Headers:** `Authorization: Bearer <access>`

**Query params:** `page`.

**200 OK**

```json
{
  "data": {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": "fac-2026-10",
        "monto": 29,
        "moneda": "USD",
        "estado": "pagada",
        "periodo_inicio": "2026-10-04T00:00:00Z",
        "periodo_fin": "2026-11-04T00:00:00Z",
        "url_pdf": "https://cloudvault.app/facturas/fac-2026-10.pdf"
      }
    ]
  }
}
```

---

## Apéndice A — Resumen implementado vs. pendiente

| # | Endpoint | Método | Estado |
| --- | --- | --- | --- |
| 1.1 | `/api/v1/auth/registro/` | POST | ✅ Implementado |
| 1.2 | `/api/v1/auth/login/` | POST | ✅ Implementado |
| 1.3 | `/api/v1/auth/recuperar-contrasena/` | POST | ✅ Implementado (formato `mensaje`, no modificar) |
| 1.4 | `/api/v1/auth/refresh/` | POST | 🆕 Pendiente |
| 1.5 | `/api/v1/auth/logout/` | POST | 🆕 Pendiente |
| 2.1 | `/api/v1/auth/perfil/` | GET | 🆕 Pendiente |
| 2.2 | `/api/v1/auth/perfil/` | PATCH | 🆕 Pendiente |
| 2.3 | `/api/v1/auth/cambiar-contrasena/` | POST | 🆕 Pendiente |
| 2.4 | `/api/v1/auth/cambiar-palabra-secreta/` | POST | 🆕 Pendiente |
| 2.5 | `/api/v1/auth/preferencias/` | GET | 🆕 Pendiente |
| 2.6 | `/api/v1/auth/preferencias/` | PATCH | 🆕 Pendiente |
| 3.1 | `/api/v1/carpetas/` | GET | 🆕 Pendiente |
| 3.2 | `/api/v1/carpetas/` | POST | 🆕 Pendiente |
| 3.3 | `/api/v1/carpetas/{id}/` | GET | 🆕 Pendiente |
| 3.4 | `/api/v1/carpetas/{id}/` | PATCH | 🆕 Pendiente |
| 3.5 | `/api/v1/carpetas/{id}/` | DELETE | 🆕 Pendiente |
| 3.6 | `/api/v1/archivos/` | GET | 🆕 Pendiente |
| 3.7 | `/api/v1/archivos/{id}/` | GET | 🆕 Pendiente |
| 3.8 | `/api/v1/archivos/{id}/` | PATCH | 🆕 Pendiente |
| 3.9 | `/api/v1/archivos/{id}/` | DELETE | 🆕 Pendiente |
| 3.10 | `/api/v1/archivos/{id}/mover/` | POST | 🆕 Pendiente |
| 3.11 | `/api/v1/unidad/resumen/` | GET | 🆕 Pendiente |
| 4.1 | `/api/v1/archivos/iniciar-carga/` | POST | 🆕 Pendiente |
| 4.2 | `/api/v1/archivos/{id}/confirmar-carga/` | POST | 🆕 Pendiente |
| 4.3 | `/api/v1/archivos/{id}/estado-carga/` | GET | 🆕 Pendiente |
| 5.1 | `/api/v1/archivos/{id}/descarga/` | GET | 🆕 Pendiente |
| 5.2 | `/api/v1/archivos/{id}/vista-previa/` | GET | 🆕 Pendiente |
| 6.1 | `/api/v1/enlaces-compartidos/` | POST | 🆕 Pendiente |
| 6.2 | `/api/v1/enlaces-compartidos/` | GET | 🆕 Pendiente |
| 6.3 | `/api/v1/enlaces-compartidos/{id}/` | DELETE | 🆕 Pendiente |
| 6.4 | `/api/v1/publico/{token}/` | GET | 🆕 Pendiente (sin auth) |
| 7.2 | `/api/v1/unidad/actividad/` | GET | 🆕 Pendiente |
| 7.3 | `/api/v1/recientes/` | GET | 🆕 Pendiente |
| 8.1 | `/api/v1/papelera/` | GET | 🆕 Pendiente |
| 8.2 | `/api/v1/papelera/{id}/restaurar/` | POST | 🆕 Pendiente |
| 8.3 | `/api/v1/papelera/{id}/` | DELETE | 🆕 Pendiente |
| 9.1 | `/api/v1/compartidos-conmigo/` | GET | 🆕 Pendiente |
| 10.1 | `/api/v1/planes/` | GET | 🆕 Pendiente |
| 10.2 | `/api/v1/mi-plan/` | GET | 🆕 Pendiente |
| 10.3 | `/api/v1/mi-plan/suscribir/` | POST | 🆕 Pendiente |
| 10.4 | `/api/v1/mi-plan/facturas/` | GET | 🆕 Pendiente |

## Apéndice B — Notas de integración con el Frontend

- **Sesión en memoria:** `authService.ts` guarda la sesión solo en memoria
  (`sesionActiva`) y el access token expira en 15 minutos. Al implementar
  `/api/v1/auth/refresh/` se recomienda agregar un interceptor de Axios que
  renueve el token de forma transparente.
- **Errores:** el Frontend lee directamente `error.response.data.error.code` y
  `error.response.data.error.fields`, por lo que el formato de la sección 0.3 es
  obligatorio.
- **Códigos anticipados:** el Frontend ya maneja `RATE_LIMITED` y
  `SERVICE_UNAVAILABLE`; el backend debería emitirlos (p. ej. con throttling).
- **TODOs reemplazados por estos contratos:**
  - `DashboardPage.tsx:61` → 5.1 (descarga)
  - `DashboardPage.tsx:94` → 3.2 (crear carpeta)
  - `DashboardPage.tsx:100` → 4.1 (carga)
  - `ProfilePage.tsx:56` → 2.2 (perfil)
  - `ModalCompartir.tsx:16` → 6.1 (enlaces)
  - `PlanesPage.tsx:265` → 10.3 (suscribir)
  - `DashboardLayout.tsx:51` → 3.11 / 10.2 (almacenamiento)
