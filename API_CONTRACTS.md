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

### 3.1 `GET /api/v1/carpetas/` — ✅ Implementado

**Headers:** `Authorization: Bearer <access>`

**Query params opcionales**

| Param | Tipo | Descripción |
| --- | --- | --- |
| `page` | int | Número de página (paginación) |
| `padre` | uuid o `null` | Filtra por carpeta padre; `null` devuelve solo las carpetas raíz. Ausente = todas. |

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
        "padre_id": null,
        "ruta_completa": "/Documentos",
        "cantidad_archivos": 2,
        "creado_en": "2026-08-01T10:00:00Z"
      },
      {
        "id": "proyectos",
        "nombre": "Proyectos",
        "color": "#7C3AED",
        "color_fondo": "#F5F3FF",
        "padre_id": null,
        "ruta_completa": "/Proyectos",
        "cantidad_archivos": 2,
        "creado_en": "2026-08-02T10:00:00Z"
      }
    ]
  }
}
```

> Cada carpeta expone `padre_id` (uuid del padre, `null` en la raíz) y
> `ruta_completa` (ruta absoluta calculada, p. ej. `/Documentos/Contratos 2026`).

**401** `NO_AUTENTICADO`

```json
{ "error": { "code": "NO_AUTENTICADO" } }
```

### 3.2 `POST /api/v1/carpetas/` — ✅ Implementado

Resuelve el `TODO(backend)` de `DashboardPage.tsx:94`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "nombre": "Contratos 2026",
  "color": "#2563EB",
  "color_fondo": "#EFF6FF",
  "padre_id": "documentos"
}
```

`color` y `color_fondo` son opcionales; si no se envían, el backend asigna una
paleta por defecto (equivalent al arreglo `COLORES_CARPETA_NUEVA` del Frontend).
`padre_id` es opcional (`null` o ausente crea la carpeta en la raíz).

**201 Created**

```json
{
  "data": {
    "id": "carpeta-1700000000000",
    "nombre": "Contratos 2026",
    "color": "#2563EB",
    "color_fondo": "#EFF6FF",
    "padre_id": "documentos",
    "ruta_completa": "/Documentos/Contratos 2026",
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

### 3.3 `GET /api/v1/carpetas/{id}/` — ✅ Implementado

**Headers:** `Authorization: Bearer <access>`

**200 OK** — mismo objeto que en el listado.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.4 `PATCH /api/v1/carpetas/{id}/` — ✅ Implementado

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
    "padre_id": "documentos",
    "ruta_completa": "/Documentos/Contratos 2026 (cerrados)",
    "cantidad_archivos": 0,
    "creado_en": "2026-10-04T18:30:00Z"
  }
}
```

**404** `NO_ENCONTRADO` / **403** `SIN_PERMISO`

```json
{ "error": { "code": "SIN_PERMISO" } }
```

### 3.5 `DELETE /api/v1/carpetas/{id}/` — ✅ Implementado

Elimina la carpeta. Los archivos dentro se mueven a "Sin carpeta" (o a la
papelera, según se defina con el equipo).

**Headers:** `Authorization: Bearer <access>`

**204 No Content** — sin cuerpo.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.5.1 `GET /api/v1/carpetas/{id}/contenido/` — ✅ Implementado

Devuelve el contenido directo de una carpeta: sus subcarpetas y sus archivos.

**Headers:** `Authorization: Bearer <access>`

**200 OK**

```json
{
  "data": {
    "subcarpetas": [
      {
        "id": "contratos",
        "nombre": "Contratos 2026",
        "color": "#2563EB",
        "color_fondo": "#EFF6FF",
        "padre_id": "documentos",
        "ruta_completa": "/Documentos/Contratos 2026",
        "cantidad_archivos": 0,
        "creado_en": "2026-10-04T18:30:00Z"
      }
    ],
    "archivos": [
      {
        "id": "1",
        "nombre_original": "Arquitectura_PaaS_v1.pdf",
        "tamano_bytes": 4404019,
        "tipo_mime": "application/pdf",
        "carpeta_id": "documentos",
        "creado_en": "2026-10-04T16:30:00Z"
      }
    ]
  }
}
```

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.5.2 `POST /api/v1/carpetas/{id}/mover/` — ✅ Implementado

Mueve una carpeta (y a todo su subárbol) a otra carpeta o a la raíz. Actualiza
`ruta_completa` en los descendientes y rechaza mover una carpeta dentro de sí
misma o de una de sus subcarpetas.

**Headers:** `Authorization: Bearer <access>`

**Body** (`padre_id: null` = raíz)

```json
{ "padre_id": "documentos" }
```

**200 OK**

```json
{
  "data": {
    "id": "carpeta-1700000000000",
    "nombre": "Contratos 2026",
    "color": "#2563EB",
    "color_fondo": "#EFF6FF",
    "padre_id": "documentos",
    "ruta_completa": "/Documentos/Contratos 2026",
    "cantidad_archivos": 0,
    "creado_en": "2026-10-04T18:30:00Z"
  }
}
```

**400** `VALIDATION_ERROR` (destino inexistente, ciclo o nombre duplicado)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "fields": {
      "padre_id": ["La carpeta indicada no existe."]
    }
  }
}
```

### 3.6 `GET /api/v1/archivos/` — ✅ Implementado

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

### 3.7 `GET /api/v1/archivos/{id}/` — ✅ Implementado

**Headers:** `Authorization: Bearer <access>`

**200 OK** — mismo objeto que en el listado.

**404** `NO_ENCONTRADO`

```json
{ "error": { "code": "NO_ENCONTRADO" } }
```

### 3.8 `PATCH /api/v1/archivos/{id}/` — ✅ Implementado

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

### 3.10 `POST /api/v1/archivos/{id}/mover/` — ✅ Implementado

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

### 5.2 `GET /api/v1/archivos/{id}/vista-previa/` — ✅ Implementado (miembros e invitados, §6.8)

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

## 6. Compartir archivos y carpetas (personas y enlaces)

Funciona como Google Drive. Este contrato **sustituye** a `docs/CONTRATO_API.md` §4 (`sharing`). Lo implementa la app `backend/compartir/` sobre las tablas de `database/compartir.sql`.

**Niveles de acceso** (`rol` + `permite_descarga`):

| Nivel en la UI | `rol` / `tipo_permiso` | `permite_descarga` | Recursos |
|---|---|---|---|
| Solo ver | `LECTURA` | `false` | archivo o carpeta |
| Ver y descargar | `LECTURA` | `true` | archivo o carpeta |
| Editor (puede subir) | `ESCRITURA` | siempre `true` | solo carpetas |

**Reglas comunes:**
- Una carpeta se comparte con todo su contenido.
- Solo administra el recurso el dueño del espacio; si no lo es, recibe **404** `NO_ENCONTRADO`.
- Los recursos se identifican con `archivo_id` **o** `carpeta_id` (UUID), nunca con los dos. Si llegan ambos o ninguno, la respuesta es **400** `VALIDATION_ERROR` en `non_field_errors`.
- Las subidas de un editor consumen la cuota del dueño.

**Fuera de alcance:** notificar por correo, descargar en ZIP, que un editor vuelva a compartir y transferir la propiedad.

### 6.1 `GET /api/v1/enlaces-compartidos/?archivo_id=|carpeta_id=` — ✅ Implementado

Devuelve el enlace del recurso (hay como mucho uno por recurso), o `null` si no tiene.

```json
{
  "data": {
    "id": "…uuid…",
    "token": "Qm9…43 caracteres",
    "archivo_id": null,
    "carpeta_id": "…uuid…",
    "rol": "LECTURA",
    "permite_descarga": true,
    "requiere_password": false,
    "fecha_expiracion": null,
    "fecha_creacion": "2026-10-30T15:00:00Z"
  }
}
```

La URL que se comparte la arma el frontend: `https://<frontend>/s/{token}`. El token se guarda en claro y solo puede leerlo el dueño.

### 6.2 `POST /api/v1/enlaces-compartidos/` — ✅ Implementado

Crea el enlace (**201**) o actualiza el existente (**200**). El token se conserva.

```json
{ "carpeta_id": "…uuid…", "rol": "ESCRITURA", "permite_descarga": true,
  "fecha_expiracion": "2026-11-30T23:59:59Z", "password": "opcional" }
```

- `fecha_expiracion`: ISO 8601 futura, o `null` para que no caduque. Una fecha pasada devuelve **400**.
- `password`: si se **omite**, se conserva la actual; `null` o `""` la quitan. Admite hasta 128 caracteres. Cambiarla o quitarla invalida los accesos ya concedidos (6.10).
- `ESCRITURA` en un archivo devuelve **400** en `rol`.

### 6.3 `DELETE /api/v1/enlaces-compartidos/{id}/` — ✅ Implementado

**204.** Desactiva el enlace. Las personas que se unieron por él pierden el acceso, salvo que el dueño haya editado su permiso (6.6).

### 6.4 `GET /api/v1/permisos-recurso/?archivo_id=|carpeta_id=` — ✅ Implementado

Personas con acceso al recurso, ordenadas por antigüedad.

```json
{ "data": [ { "id": 12, "usuario": { "id": "…uuid…", "correo": "ana@x.com", "nombre": "Ana" },
              "tipo_permiso": "LECTURA", "permite_descarga": false,
              "via_enlace": true, "fecha_creacion": "…" } ] }
```

`via_enlace: true` indica que la persona abrió el enlace con su sesión iniciada. En ese caso, su nivel es el del enlace y caduca con él.

### 6.5 `POST /api/v1/permisos-recurso/` — ✅ Implementado

```json
{ "archivo_id": "…uuid…", "correo": "ana@x.com", "tipo_permiso": "LECTURA", "permite_descarga": true }
```

- Responde **201** si es un permiso nuevo y **200** si la persona ya tenía uno, que se reemplaza.
- Si el correo no pertenece a un usuario activo o es de un miembro del propio espacio, responde **400** con el error en `correo`.

### 6.6 `PATCH /api/v1/permisos-recurso/{id}/` · `DELETE /api/v1/permisos-recurso/{id}/` — ✅ Implementado

- El `PATCH` acepta `tipo_permiso` y/o `permite_descarga` y responde **200** con el permiso. Un permiso obtenido por enlace pasa a ser directo, de modo que sobrevive aunque el enlace se desactive.
- El `DELETE` responde **204**.

### 6.7 `GET /api/v1/compartidos-conmigo/` — ✅ Implementado

Sustituye a la antigua §9. Devuelve una lista plana, sin paginar, con lo más reciente primero. No incluye los permisos caducados ni los recursos que están en la papelera.

```json
{ "data": [ { "tipo": "carpeta", "id": "…", "nombre": "Proyecto", "rol": "ESCRITURA",
              "permite_descarga": true, "tamano_bytes": null, "tipo_mime": null } ] }
```

### 6.8 `GET /api/v1/compartidos-conmigo/carpetas/{id}/contenido/` — ✅ Implementado

Navega por una carpeta compartida (o por una de sus subcarpetas).

```json
{ "data": { "carpeta": { "id": "…", "nombre": "Proyecto", "padre_id": null },
            "rol": "ESCRITURA", "permite_descarga": true, "puede_subir": true,
            "carpetas": [ { "id": "…", "nombre": "Fotos" } ],
            "archivos": [ { "id": "…", "nombre": "a.pdf", "tamano_bytes": 1024,
                            "tipo_mime": "application/pdf", "fecha_modificacion": "…" } ] } }
```

- `padre_id` es `null` cuando el padre no es accesible, es decir, en la raíz de lo compartido.
- Para ver y descargar se usan `GET /archivos/{id}/vista-previa/` (5.2, ya implementado) y `GET /archivos/{id}/descarga/`. Ambos aceptan a los invitados; la descarga exige `permite_descarga`.
- Las subidas (§4) a una carpeta con `ESCRITURA` se aceptan.

### 6.9 `GET /api/v1/publico/{token}/` — ✅ Implementado (sesión opcional)

- Si llega `Authorization`, se usa la sesión. Un token caducado no da 401: la petición se trata como anónima.
- Si el enlace tiene contraseña y aún no se verificó, la respuesta es `{"tipo": "carpeta", "requiere_password": true}`.
- Una vez verificado, la respuesta es la siguiente:

```json
{ "data": { "tipo": "carpeta", "id": "…", "nombre": "Proyecto", "rol": "ESCRITURA",
            "permite_descarga": true, "requiere_password": false,
            "unido": true, "puede_subir": true } }
```

- Si el recurso es un archivo, la respuesta añade `tamano_bytes` y `tipo_mime`.
- Con sesión iniciada, abrir el enlace **une** al usuario (`unido: true`). Desde ese momento lo ve en *Compartidos conmigo* con el nivel del enlace.
- Subir archivos por enlace exige sesión: `puede_subir` solo es `true` con usuario autenticado y rol `ESCRITURA`.
- **404** `NO_ENCONTRADO`: el enlace no existe, se desactivó o caducó.
- Todas las rutas `/publico/` envían `Cache-Control: no-store` y `Referrer-Policy: no-referrer`, y tienen un límite de `COMPARTIR_PUBLICO_RATE` (60/min por IP, por defecto).

### 6.10 `POST /api/v1/publico/{token}/acceso/` — ✅ Implementado

Body: `{"password": "…"}`. Respuesta:

```json
{ "data": { "share_token": "…", "expira_en": "…" } }
```

- El `share_token` vale 15 minutos y se envía en la cabecera `X-Share-Token` en las rutas 6.9 a 6.12. El frontend lo guarda en `sessionStorage`.
- Una contraseña incorrecta devuelve **403** `SIN_PERMISO`.
- Tiene un límite de `COMPARTIR_PASSWORD_RATE` (10/hora por IP y enlace, por defecto); al superarlo responde **429** `RATE_LIMITED`.

### 6.11 `GET /api/v1/publico/{token}/contenido/?carpeta_id=` — ✅ Implementado

Solo para enlaces de carpeta. Tiene la misma forma que 6.8, pero sin `puede_subir`. Sin `carpeta_id` devuelve la raíz del enlace, cuyo `padre_id` es `null`.

- **403** `SIN_PERMISO`: falta la contraseña o caducó el `X-Share-Token`.
- **404**: la carpeta está fuera del enlace.

### 6.12 `GET /api/v1/publico/{token}/archivos/{id}/?accion=ver|descargar` — ✅ Implementado

Devuelve una URL temporal: `{url_vista_previa | url_descarga, nombre, tipo, expira_en}`.

- `descargar` sin `permite_descarga` devuelve **403**.
- Un archivo fuera del enlace devuelve **404**.
- Las descargas quedan registradas en la auditoría (`DESCARGA_ENLACE`).
- "Solo ver" se aplica en la interfaz y en esta ruta. La URL de vista previa permite guardar el contenido mientras está vigente, igual que una vista previa de Drive.

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

Movido a §6.7 y §6.8.

---

## 10. Módulo de Planes

Respalda `frontend/src/pages/PlanesPage.tsx`.

### 10.1 `GET /api/v1/planes/` — ✅ Implementado

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

### 10.2 `GET /api/v1/mi-plan/` — ✅ Implementado

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

### 10.3 `POST /api/v1/mi-plan/suscribir/` — ✅ Implementado

Cambia o contrata un plan con **pago simulado con tarjeta** (sin cargo real).
Los planes de pago exigen `tarjeta_id` (una tarjeta guardada de la organización, §10.5,
no vencida); el plan gratuito no la necesita. El pago queda en `historial_pagos` con
referencia `sim-<marca>-<ultimos4>-<token>`.

**Headers:** `Authorization: Bearer <access>`

**Body**

```json
{
  "plan_id": "empresarial",
  "tipo_facturacion": "anual",
  "tarjeta_id": "9b2e…"
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
      "tipo_facturacion": ["El tipo de facturación debe ser 'mensual' o 'anual'."],
      "tarjeta_id": ["Selecciona una tarjeta para pagar."]
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

### 10.5 `/api/v1/mi-plan/tarjetas/` — ✅ Implementado (pago simulado)

Tarjetas de crédito/débito de la organización, **máximo 2**. Solo el propietario.
El número y el CVV se validan (Luhn, CVV de 3 dígitos o 4 en Amex, vencimiento no pasado)
y se descartan: solo se guardan titular, marca, tipo, 4 últimos dígitos y vencimiento
(tabla `metodos_pago`, `database/metodos_pago.sql`). La primera tarjeta queda predeterminada.

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/mi-plan/tarjetas/?organizacion_id=` | Lista (sin paginar) |
| POST | `/mi-plan/tarjetas/` | Alta. 201; 409 `VALIDATION_ERROR` en `fields.tarjetas` si ya hay 2 |
| PATCH | `/mi-plan/tarjetas/{id}/` | Actualiza: `titular`, `tipo`, `mes_expiracion`/`anio_expiracion`, reemplazo con `numero`+`cvv`, o `predeterminada: true` |
| DELETE | `/mi-plan/tarjetas/{id}/?organizacion_id=` | 204; si era la predeterminada, pasa a serlo la otra |

**Body (POST)**

```json
{
  "titular": "Ana Pérez",
  "numero": "4242 4242 4242 4242",
  "cvv": "123",
  "mes_expiracion": 12,
  "anio_expiracion": 2030,
  "tipo": "credito",
  "organizacion_id": "…"
}
```

**Tarjeta (respuesta)**

```json
{
  "data": {
    "id": "9b2e…",
    "titular": "Ana Pérez",
    "marca": "visa",
    "tipo": "credito",
    "ultimos4": "4242",
    "mes_expiracion": 12,
    "anio_expiracion": 2030,
    "predeterminada": true
  }
}
```

Errores: 400 `VALIDATION_ERROR` por campo (`numero`, `cvv`, `titular`, `tipo`,
`mes_expiracion`, `anio_expiracion`); 403 si no es propietario; 404 si la tarjeta es de otra organización.

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
| 3.1 | `/api/v1/carpetas/` | GET | ✅ Implementado |
| 3.2 | `/api/v1/carpetas/` | POST | ✅ Implementado |
| 3.3 | `/api/v1/carpetas/{id}/` | GET | ✅ Implementado |
| 3.4 | `/api/v1/carpetas/{id}/` | PATCH | ✅ Implementado |
| 3.5 | `/api/v1/carpetas/{id}/` | DELETE | ✅ Implementado |
| 3.5.1 | `/api/v1/carpetas/{id}/contenido/` | GET | ✅ Implementado |
| 3.5.2 | `/api/v1/carpetas/{id}/mover/` | POST | ✅ Implementado |
| 3.6 | `/api/v1/archivos/` | GET | ✅ Implementado |
| 3.7 | `/api/v1/archivos/{id}/` | GET | ✅ Implementado |
| 3.8 | `/api/v1/archivos/{id}/` | PATCH | ✅ Implementado |
| 3.9 | `/api/v1/archivos/{id}/` | DELETE | 🆕 Pendiente |
| 3.10 | `/api/v1/archivos/{id}/mover/` | POST | ✅ Implementado |
| 3.11 | `/api/v1/unidad/resumen/` | GET | 🆕 Pendiente |
| 4.1 | `/api/v1/archivos/iniciar-carga/` | POST | 🆕 Pendiente |
| 4.2 | `/api/v1/archivos/{id}/confirmar-carga/` | POST | 🆕 Pendiente |
| 4.3 | `/api/v1/archivos/{id}/estado-carga/` | GET | 🆕 Pendiente |
| 5.1 | `/api/v1/archivos/{id}/descarga/` | GET | 🆕 Pendiente |
| 5.2 | `/api/v1/archivos/{id}/vista-previa/` | GET | ✅ Implementado |
| 6.1–6.3 | `/api/v1/enlaces-compartidos/` (+ `{id}/`) | GET, POST, DELETE | ✅ Implementado |
| 6.4–6.6 | `/api/v1/permisos-recurso/` (+ `{id}/`) | GET, POST, PATCH, DELETE | ✅ Implementado |
| 6.7–6.8 | `/api/v1/compartidos-conmigo/` (+ `carpetas/{id}/contenido/`) | GET | ✅ Implementado |
| 6.9–6.12 | `/api/v1/publico/{token}/` (+ `acceso/`, `contenido/`, `archivos/{id}/`) | GET, POST | ✅ Implementado (sesión opcional) |
| 7.2 | `/api/v1/unidad/actividad/` | GET | 🆕 Pendiente |
| 7.3 | `/api/v1/recientes/` | GET | 🆕 Pendiente |
| 8.1 | `/api/v1/papelera/` | GET | 🆕 Pendiente |
| 8.2 | `/api/v1/papelera/{id}/restaurar/` | POST | 🆕 Pendiente |
| 8.3 | `/api/v1/papelera/{id}/` | DELETE | 🆕 Pendiente |
| 10.1 | `/api/v1/planes/` | GET | ✅ Implementado |
| 10.2 | `/api/v1/mi-plan/` | GET | ✅ Implementado |
| 10.3 | `/api/v1/mi-plan/suscribir/` | POST | ✅ Implementado |
| 10.4 | `/api/v1/mi-plan/facturas/` | GET | 🆕 Pendiente |
| 10.5 | `/api/v1/mi-plan/tarjetas/` (+ `{id}/`) | GET, POST, PATCH, DELETE | ✅ Implementado (pago simulado) |

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
  - `ModalCompartir.tsx` → 6.1–6.6; `CompartidosPage.tsx` → 6.7–6.8; `EnlacePublicoPage.tsx` (`/s/:token`) → 6.9–6.12
  - `PlanesPage.tsx:265` → 10.3 (suscribir)
  - `DashboardLayout.tsx:51` → 3.11 / 10.2 (almacenamiento)

## Apéndice C — Selección de organización en el panel

`GET /api/v1/organizaciones/disponibles/` permite descubrir únicamente las
membresías actuales del usuario autenticado. Acepta `page` (desde 1) y
`page_size` (1–100, predeterminado 50); rechaza cuerpo, parámetros desconocidos
o repetidos. Responde con `Cache-Control: no-store`:

```json
{"data":{"count":1,"next":null,"previous":null,"page_size":50,"results":[
  {"id":"b0000000-0000-4000-8000-000000000001","nombre":"Equipo","nivel_rol":1}
]}}
```

Una lista vacía no crea organizaciones. El resultado no clasifica espacios
personales, no concede privilegios globales y no sustituye `/usuarios/contexto/`
ni los endpoints de administración propuestos. Los niveles existentes son
0 propietario, 1 lector, 2 operativo y 3 avanzado; cada operación conserva sus
controles del servidor. La lista de archivos incluye los archivos activos de la
organización, aunque su propietario sea otro miembro.

El panel exige elegir cuando hay varias organizaciones y solo selecciona
automáticamente una membresía única. Envía `organizacion_id` en la consulta de
archivos, carpetas, papelera, resumen, perfil y consulta del plan. La contratación
lo envía en el cuerpo. Los endpoints que autorizan por ID, como descarga y
confirmación, obtienen el ámbito del recurso o de la reserva persistida; descarga
conserva su contrato sin parámetros de consulta.

El inicio de carga admite un `organizacion_id` UUID opcional en el cuerpo.
Con ámbito explícito se valida la membresía vigente, el permiso de escritura y
que la carpeta pertenezca a esa organización. Se revalida bajo bloqueo y durante
la confirmación usando la organización guardada en la reserva. El proveedor
`storage.servicios.ProveedorStorage` implementa la capacidad opcional
`resolver_destino_organizacion`; los proveedores anteriores solo se aceptan si
su resolución inequívoca devuelve exactamente el mismo destino.

El cambio de organización reinicia el estado del panel; una mutación o carga
en curso mantiene su organización de origen y bloquea el selector hasta terminar.
La visibilidad y los permisos internos de organización se distinguen de los
enlaces externos de compartición, cuyo flujo es independiente.
