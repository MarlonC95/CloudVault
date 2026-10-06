# Guía de integración Frontend ↔ Backend (Carpetas, Archivos y Planes)

Para quien conecta el frontend con los endpoints nuevos del backend (apps `storage` y `subscriptions`).
Fuente de verdad de los contratos: `API_CONTRACTS.md` (en la raíz). Esta guía no lo reemplaza: explica **qué cambia en el frontend, en qué orden hacerlo y qué cuidar**.

## 1. Estado actual

| Área | Backend | Frontend hoy |
|---|---|---|
| Carpetas (crear, listar, detalle, renombrar, mover, eliminar, contenido) | Listo | Datos de ejemplo en `useState` |
| Archivos: listar, detalle, renombrar, mover | Listo | Datos de ejemplo |
| Planes: catálogo, plan actual, suscribir (pago simulado) | Listo | Planes y uso (45/100 GB) escritos a mano en `PlanesPage.tsx` |
| Subida de archivos (URL prefirmada S3/MinIO) | **No existe** | **Simulada** (ver §6) |
| Descarga de archivos | **No existe** | **Simulada** (ver §6) |
| Eliminar archivo → papelera, restaurar | **No existe** | Simulado con `setState` (`enPapelera: true`) |
| Resumen de almacenamiento (`/unidad/resumen/`) | **No existe** | Valores fijos en `DashboardLayout.tsx` |
| Compartir (enlaces públicos) | **No existe** | Simulado (`ModalCompartir.tsx`) |
| `POST /auth/refresh/` y `/auth/logout/` | **Pendiente (módulo auth)** | Sin interceptor |

El frontend actual **no rompe** con el backend nuevo porque todavía no lo llama. Todo lo de abajo es el trabajo de conectarlo.

## 2. Convenciones del backend (no cambian en ningún endpoint)

- Base: `http://127.0.0.1:8000/api/v1/` (el frontend ya resuelve `API_BASE_URL` en `authService.ts`).
- Todo endpoint nuevo exige `Authorization: Bearer <access>`. Sin él: `401 {"error":{"code":"NO_AUTENTICADO"}}`; token vencido o inválido: `401 TOKEN_INVALIDO`.
- Éxito: `{ "data": ... }`. Listados paginados: `{ "data": { "count", "next", "previous", "results": [...] } }` (50 por página, `?page=N`).
- Error: `{ "error": { "code": "...", "fields": { "campo": ["mensaje"] } } }` (`fields` solo en validación). El frontend ya lee `error.response.data.error.code/fields`.
- Excepción: `DELETE` responde `204` sin cuerpo útil. No intentes leer `data` en un 204.
- Recurso de otro usuario o inexistente → `404 NO_ENCONTRADO` (no hay 403 para evitar enumeración).
- Nombre duplicado de carpeta → **409** pero con `code: "VALIDATION_ERROR"` y `fields.nombre` (así lo define el contrato). Atiende el código y el status, no solo uno.
- Fechas en ISO 8601 UTC; el frontend las convierte a "Hace 2 horas".

## 3. Cambios de forma de datos (el mapeo)

El backend usa `snake_case` y datos crudos; el frontend usa `camelCase` y textos ya formateados.

### Carpeta
| Backend (`carpetas`) | Frontend (`Carpeta`) | Nota |
|---|---|---|
| `id` (UUID string) | `id` | Sigue siendo `string`; el código solo compara igualdad |
| `nombre`, `color` | igual | |
| `color_fondo` | `colorFondo` | |
| `cantidad_archivos` | (hoy se calcula filtrando en memoria) | Usar el valor del backend; excluye archivos en papelera |
| `padre_id`, `ruta_completa` | (nuevo) | Extensión para carpetas anidadas; la UI actual puede ignorarlos |
| `creado_en` | (nuevo) | |

### Archivo
| Backend (`archivos`) | Frontend (`Archivo`) | Nota |
|---|---|---|
| `id` | `id` | |
| `nombre` | `nombre` | |
| `tipo` | `tipo` | `pdf, zip, png, js, xlsx, mp4, docx` u `otro`; coincide con `TipoArchivo` |
| `tamano_bytes` | (nuevo) | **Úsalo para formatear** con `formatearTamanoBytes` |
| `tamano_legible` | `tamano` | Llega con punto decimal como el contrato (`"4.2 MB"`, `"128 MB"`); corregido, ver `docs/PROBLEMA_TAMANO_LEGIBLE.md`. Aun así conviene formatear desde `tamano_bytes` |
| `fecha_modificacion` (ISO) | `fechaModificacion` (texto relativo) | Formatear en cliente |
| `propietario` `{id, nombre_completo}` | `propietario` (string) | Mapear a `propietario.nombre_completo` |
| `cifrado`, `es_nuevo`, `en_papelera` | `cifrado`, `esNuevo`, `enPapelera` | |
| `carpeta_id` (`null` = sin carpeta) | `carpetaId` | |

### Plan
| Backend (`planes`) | Frontend (`Plan` en `PlanesPage`) | Nota |
|---|---|---|
| `id` `gratuito|pro|empresarial` | `id: NivelPlan` | Ya coincide |
| `precio_mensual` | `precioBase` | |
| `precio_anual` | (hoy `Math.round(precioBase*0.8)`) | **Semántica distinta:** el backend da el **total anual** (29 → 278). La UI muestra precio **por mes** con 20% off: usar `Math.round(precio_anual / 12)` (= 23) |
| `almacenamiento_bytes` (`null` = ilimitado), `almacenamiento_legible` | | |
| `es_popular`, `caracteristicas[]` | | Reemplazan la lista fija |

## 4. Endpoints listos y cómo se usan

Carpetas (`/api/v1/carpetas/`)
- `GET /` lista **todas** las carpetas del usuario (plano, como la UI actual). Opcional `?padre=<id>` o `?padre=null` (raíz).
- `POST /` `{nombre, color?, color_fondo?}` → 201. Sin colores asigna paleta por defecto.
- `GET /{id}/`, `PATCH /{id}/` (renombrar/recolorear), `DELETE /{id}/` (204; los archivos quedan "Sin carpeta" y las subcarpetas se eliminan).
- `GET /{id}/contenido/` → `{subcarpetas: [...], archivos: [...]}`.
- `POST /{id}/mover/` `{padre_id: <id|null>}`; rechaza mover a sí misma o a una subcarpeta (`400 VALIDATION_ERROR`, `fields.padre_id`).

Archivos (`/api/v1/archivos/`)
- `GET /` con `?carpeta=<id|null>`, `?busqueda=`, `?tipo=pdf|zip|png|js|xlsx|mp4|docx|otro`. No incluye archivos en papelera.
- `GET /{id}/`, `PATCH /{id}/` `{nombre}` (renombrar), `POST /{id}/mover/` `{carpeta_id: <id|null>}` (200 con `id, nombre, carpeta_id, fecha_modificacion`).

Planes
- `GET /planes/` catálogo de 3 planes.
- `GET /mi-plan/` plan actual, `estado`, `renueva_en` y `almacenamiento` (`usado_bytes`, `cuota_bytes` —`null` si ilimitado—, `porcentaje_usado`, legibles). Si el usuario no tiene suscripción se crea el plan gratuito.
- `POST /mi-plan/suscribir/` `{plan_id, tipo_facturacion: "mensual"|"anual"}` → 200. Bajar a un plan con menos cuota que el uso actual → `409 CUOTA_EXCEDIDA` con `fields.plan_id` (mostrar el mensaje).

## 5. Qué cambia en cada pantalla

`DashboardPage.tsx`
- Carga inicial: reemplazar `CARPETAS_EJEMPLO` / `ARCHIVOS_EJEMPLO` por `GET /carpetas/` y `GET /archivos/` (con `?carpeta=` según `carpetaActivaId`).
- `contarArchivosDeCarpeta` (línea ~46): usar `cantidad_archivos`.
- Crear carpeta (línea ~94, hoy ID inventado): `POST /carpetas/` y usar el objeto devuelto; ante 409 mostrar `fields.nombre`.
- Mover archivo (línea ~81): `POST /archivos/{id}/mover/`; después refrescar datos.
- Filtros por búsqueda/tipo/fecha/tamaño: hoy son locales; `busqueda`, `tipo` y `carpeta` ya pueden ir al backend. `fecha` y `tamano` (rangos) **no** tienen soporte en el backend aún, mantenerlos locales por ahora.
- Eliminar, descargar, subir, compartir: siguen simulados (ver §6 y §7).

`PlanesPage.tsx`: leer `/planes/` y `/mi-plan/`; el botón "Actualizar Plan" llama a `suscribir` y luego refresca `/mi-plan/`. Resuelve el TODO del contrato 10.3.

`DashboardLayout.tsx` (barra de almacenamiento): hoy fija. Mientras no exista `/unidad/resumen/`, usar `almacenamiento` de `GET /mi-plan/` (trae usado, cuota y porcentaje).

## 6. Subida y descarga: qué es simulado y qué falta

Lo que probaste (subir un archivo y descargar otro) funciona **solo en el navegador**:
- **Subir** (`manejarConfirmarSubida`, `DashboardPage.tsx` ~100): crea objetos `Archivo` en `useState` con id `subido-<timestamp>`. El `File` real **no sale del navegador**: no hay petición, no se guarda nada y al recargar desaparece. La cola flotante de progreso usa `CARGAS_EJEMPLO` fijo, no un progreso real.
- **Descargar** (`manejarDescargar`, ~60): genera un `Blob` de texto ("Archivo de ejemplo generado por CloudVault…") y lo baja con el nombre del archivo. No es el contenido real.

El backend **no tiene** nada de esto todavía: no existe `iniciar-carga`, `confirmar-carga`, `descarga` ni `vista-previa`, ni integración con MinIO/S3 (no hay `boto3` en `requirements.txt`). Hoy el backend solo guarda **metadatos** (`FileMetadata`); no hay binarios.

Flujo real previsto (contrato §4–5), para cuando exista:
1. `POST /archivos/iniciar-carga/` con `{nombre, tamano_bytes, tipo_mime, carpeta_id}` → `{archivo_id, url_subida, metodo: "PUT", encabezados, expira_en}` (409 `CUOTA_EXCEDIDA` si no cabe).
2. El navegador hace `PUT` **directo** a `url_subida` con el binario y los `encabezados` (aquí sale el progreso real, MB/s; **no** pasa por Django ni lleva el token).
3. `POST /archivos/{id}/confirmar-carga/` → el archivo aparece en el listado y cuenta en la cuota.
4. Descarga: `GET /archivos/{id}/descarga/` → `{url_descarga, nombre, expira_en}`; el frontend abre esa URL temporal.

Mientras tanto, con backend conectado: la tabla de archivos saldrá **vacía** para usuarios reales (no hay forma de crear `FileMetadata` por API). Dejar subir/descargar simulados y marcarlos claramente, o preparar el flujo contra un backend de prueba.

## 7. Otros huecos conocidos

- `DELETE /archivos/{id}/` (papelera), `/papelera/`, restaurar: pendientes en backend. `manejarEliminar` sigue local.
- Compartir (`/enlaces-compartidos/`): pendiente.
- Paginación: más de 50 resultados llegan en otra página; hoy la UI no la maneja (para carpetas/archivos del usuario puede bastar con pedir más páginas o implementar "cargar más").
- Sesión: el access token dura 15 min y `refresh` aún no existe; sin él la sesión se cae a los 15 min (dependencia con el módulo de auth).
- IDs: son UUID (por ejemplo `3f2c…`), nunca `documentos`. No usar ids como claves de negocio ni rutas escritas a mano.

## 8. Capa de servicios recomendada (para tener en mente)

Hoy los componentes mezclan estado, datos de ejemplo y lógica. La propuesta es separar en capas para que las páginas casi no sepan de HTTP ni de `snake_case`. **No está implementada**; es una sugerencia para que quien haga el frontend la considere. Encaja con el stack de la propuesta (Axios + TanStack Query).

Estructura sugerida:

```
frontend/src/
  services/
    apiClient.ts          # instancia de Axios + interceptores (token y 401)
    carpetasService.ts    # funciones: listar, crear, renombrar, mover, eliminar, contenido
    archivosService.ts    # listar, obtener, renombrar, mover (más adelante: iniciarCarga, confirmarCarga, descargar)
    planesService.ts      # listarPlanes, obtenerMiPlan, suscribir
    mapeadores.ts         # snake_case/API -> tipos del frontend (y viceversa)
    tiposApi.ts           # tipos de las respuestas tal cual las manda el backend
  hooks/
    useCarpetas.ts        # TanStack Query: useQuery/useMutation sobre los servicios
    useArchivos.ts
    useMiPlan.ts
```

Responsabilidad de cada pieza:
- **`apiClient.ts`**: una sola instancia de Axios con `baseURL = API_BASE_URL + '/api/v1'`. Interceptor de petición: añade `Authorization: Bearer <accessToken>` desde la sesión en memoria de `authService.ts` (exponer un `obtenerAccessToken()`). Interceptor de respuesta: ante `401 TOKEN_INVALIDO`, llamar a `POST /auth/refresh/` una vez y reintentar la petición original; si falla, cerrar sesión y llevar a `/login`. (Sección "Apéndice B" de `API_CONTRACTS.md` ya pide este interceptor.) Hasta que `refresh` exista, el interceptor solo debería cerrar sesión ante el 401.
- **`tiposApi.ts`**: describe exactamente lo que devuelve el backend (`CarpetaApi`, `ArchivoApi`, `PlanApi`, `Paginado<T>` = `{count,next,previous,results}`, `RespuestaApi<T>` = `{data: T}`, `ErrorApi`). Así un cambio de contrato se ve en un solo sitio.
- **`mapeadores.ts`**: funciones puras `carpetaDesdeApi`, `archivoDesdeApi`, `planDesdeApi`. Aquí viven las conversiones de §3 (`color_fondo→colorFondo`, `carpeta_id→carpetaId`, `propietario.nombre_completo→propietario`, formatear `tamano` desde `tamano_bytes`, fecha ISO→texto relativo, `precio_anual/12`). Los tipos de `types/archivo.ts` pueden quedarse casi igual; el mapper absorbe la diferencia, y los componentes (`TarjetaCarpeta`, `TablaArchivos`, `ModalMoverArchivo`…) no se tocan.
- **`*Service.ts`**: funciones `async` que llaman al `apiClient`, desenvuelven `data` y devuelven tipos del frontend ya mapeados. Normalizan errores a un solo formato (`{codigo, campos}`), igual que hace `authService.ts` con `RespuestaErrorApi`, para que los componentes solo muestren `campos.nombre` o un mensaje por `codigo`. Los `DELETE` (204) no deben intentar leer `data`.
- **Hooks con TanStack Query** (`useCarpetas`, `useArchivos({carpetaId, busqueda, tipo})`, `useMiPlan`): `useQuery` con claves como `['carpetas']`, `['archivos', filtros]`, `['mi-plan']`; `useMutation` para crear/renombrar/mover que, al terminar, hace `invalidateQueries` para refrescar listas y contadores (`cantidad_archivos`, barra de almacenamiento). Esto reemplaza los `setCarpetas`/`setArchivos` manuales de `DashboardPage`.

Orden de integración sugerido (cada paso se puede probar solo):
1. `apiClient` + token (probar con `GET /planes/` y un token real).
2. Planes: `planesService` + `PlanesPage` (el más simple; sin archivos).
3. Carpetas: listar y crear; luego renombrar, mover y eliminar.
4. Archivos: listar con filtros, renombrar, mover.
5. Barra de almacenamiento desde `GET /mi-plan/`.
6. Más adelante: subida/descarga reales, papelera, compartir (cuando el backend los tenga).

Beneficios: un solo lugar donde cambia el contrato, componentes visuales sin cambios de props, estado del servidor manejado por TanStack Query (caché y refresco) en vez de `useState`, y errores uniformes.

Riesgos a vigilar:
- Quien haga la integración debe coordinarse con el módulo de auth por `refresh`; sin él, el interceptor no puede renovar.
- No mezclar a la vez datos de ejemplo y datos reales en la misma lista (ids distintos, UUID contra `'1'`).
- Mantener `cargas` (cola de subida) separado hasta que exista la subida real.

## 9. Cómo probar el backend localmente

Ver `README.md` (instalación, `migrate`, `runserver`, `manage.py test`). Flujo rápido: registro → login (copiar `data.tokens.access`) → llamar a los endpoints con `Authorization: Bearer <access>`. CORS ya permite `http://localhost:5173` y `http://127.0.0.1:5173`.
