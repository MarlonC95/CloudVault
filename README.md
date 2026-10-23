# CloudVault
CloudVault es una plataforma web de almacenamiento como servicio (PaaS) que permite la gestión segura de archivos, control de acceso basado en roles (RBAC), enlaces temporales compartidos y papelera lógica con retención de 30 días. Desarrollada con React, Django REST Framework, PostgreSQL y almacenamiento desacoplado con URLs prefirmadas (S3/MinIO)

## Desarrollo con Docker

El entorno integra frontend y backend con los módulos de autenticación, almacenamiento, carpetas, papelera y suscripciones. Configura `backend/.env` con PostgreSQL y S3 y ejecuta desde la raíz:

```sh
docker compose up -d --build --wait --wait-timeout 180
```

Frontend: http://localhost:5173 · API y Swagger: http://localhost:8000/api/docs/

Consulta [la guía Docker](docs/DOCKER.md) para actualizar tras cada módulo, ejecutar las pruebas aisladas y diagnosticar los servicios sin modificar la base compartida.
