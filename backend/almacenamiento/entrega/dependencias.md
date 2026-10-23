# Dependencias para la prueba conjunta

Esta lista acompaña el contrato de fase 9; describe trabajo pendiente y criterio verificable. No se envió mensaje al equipo, se modificó su código ni se aplicó SQL compartido.

| Responsable | Dependencia pendiente | Evidencia requerida |
|---|---|---|
| German | Fábrica real de destino, permiso, plan/cuota, registro de archivo, descarga y referencias técnicas | Path importable real, mismas identidades/alias SQL, carga y lectura autorizadas con datos del módulo real |
| German + Marlon | Autoridad única de usado, semántica de papelera y escritores coordinados | Una publicación consume S exactamente una vez, todos los escritores adoptan el lock y no referencian claves terminales |
| Marlon | Esquema técnico de 13 tablas, prerrequisitos, diario y permisos complementarios | Inspección compatible, diario disponible antes de COPY, revisión del rol de escritura y sesión PostgreSQL |
| Marlon + auth | Referencia `usuarios.creado_en` frente a ORM/despliegue `fecha_creacion` | Alineación versionada acordada, login/registro/recuperación aprobados en el esquema final |
| Dani + responsable del ambiente | Mantenimiento supervisado y CORS del origen frontend definitivo | Intervalo/backlog observados, política autorizada, PUT/GET/ETag desde ese origen; sin borrados no autorizados |
| Mily | Sustituir mocks React y consumir las tres rutas/headers/UTC/errores | Carga, confirmación, descarga y recuperación de fallos usando React real |
| Equipo | F04 de fase 8: reconstrucción y reinicio del despliegue | Reproducción desde el entorno final con recuperación durable, sin inferirlo del reinicio privado |

## Contrato que implementa el proveedor de German

`ALMACENAMIENTO_SERVICIOS_FACTORY` apunta a una función sin argumentos que devuelve el proveedor de [integracion.py](../integracion.py). `using` debe ser `default`, PostgreSQL compartido con las tablas técnicas. Métodos:

- `resolver_destino(solicitante_id, carpeta_id)` devuelve `DestinoAutorizado` con UUID de actor, organización y carpeta; revalida pertenencia/permisos actuales. Raíz necesita un único ámbito habilitado. Propietario rol 0 no se excluye por usar solo `rol >= 2`.
- `bloquear_cuota(organizacion_id)` produce contexto de bloqueo SQL estable, dentro de la transacción de Dani y compartido por todos los escritores.
- `leer_cuota(organizacion_id)` devuelve `CuotaVigente` actual bajo lock: organización/plan activos, período vigente, límite/usado válidos y una política sin suscripciones ambiguas. No inventar cuota personal ni valores centinela para ilimitado.
- `registrar_archivo(archivo)` utiliza modelos reales con el mismo archivo UUID, organización/carpeta/autor, clave final, tamaño, MIME y hash verificados; todo en la transacción final. U debe cambiar una vez por S, por una sola autoridad (trigger o proveedor). Dani verifica y no añade un segundo incremento.
- `autorizar_descarga(solicitante_id, archivo_id)` devuelve `ArchivoVerificado` accesible con permisos/papelera actuales; descarga reautoriza después de HEAD. No devuelve temporales ni toma claves del cliente.
- `inspeccionar_objeto_tecnico(sesion_id, organizacion_id, clave)` inspecciona referencias **globales**, incluyendo papelera/otros actores, mediante SQL local coordinado. `copia_concluida` requiere evidencia; ni edad, 404 ni lock perdido demuestran que COPY terminó.

Los parámetros son keyword-only según el protocolo. No hacer PUT/GET/HEAD/COPY, transferencias o callback remoto bajo cuota/transacción SQL. Reclamo de publicador → cuota → sesión → intento → metadatos; inicio toma primero lock de inicios por actor. Las sesiones técnicas no sustituyen el CRUD. La fábrica sintética de tests no es implementación ni solución temporal para producción.

## Registro de prueba con Mily

Pendiente de colaboración. Al realizarla, registrar fecha UTC, commit de backend/cliente, origen frontend, perfil SQL/S3, casos y resultados sin tokens/URLs. Comprobar éxito y fallo de confirmación tras PUT, expiración, 401/403/409/429, conservación de ID, descarga/bytes y listado/cuota del módulo de German. Actualizar evidencia con lo observado; no marcar integración por haber importado OpenAPI o aprobado dobles.
