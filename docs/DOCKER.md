# Docker de CloudVault

El entorno de desarrollo mantiene dos imágenes: `cloudvault-backend:dev` (Django, autenticación, almacenamiento, carpetas, papelera y suscripciones) y `cloudvault-frontend:dev` (React/Vite). PostgreSQL y S3 siguen siendo los servicios externos ya configurados; no se reemplazan ni se inicializan al arrancar.

## Requisitos y configuración

- Docker y Docker Compose con el motor iniciado.
- En Docker Desktop: `docker desktop start`. Si el contexto activo no apunta a Desktop, usar `docker --context desktop-linux compose ...` en los comandos siguientes.
- `backend/.env` configurado a partir de `backend/.env.example`. No se copia a las imágenes ni se versiona.
- Django necesita `DJANGO_SECRET_KEY` y `DATABASE_URL` (o las variables `DB_*`).
- El almacenamiento Railway necesita `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`.
- El rol PostgreSQL debe tener los permisos del esquema SQL instalado. Los modelos son `managed = False`: no ejecutar `manage.py migrate` ni aplicar SQL automáticamente contra la base compartida.
- El CORS del bucket debe permitir los orígenes del navegador (`http://localhost:5173` y/o `http://127.0.0.1:5173`) para las cargas PUT y descargas GET. El arranque Docker no modifica esa política.

Compose usa `backend/.env` como única fuente de configuración privada. Para usar otro archivo completo, se puede anteponer `CLOUDVAULT_ENV_FILE=./backend/.env.docker` al comando. Un `.env.docker` antiguo de solo login no basta para el módulo S3. No es necesario duplicar ni editar credenciales si el `.env` existente ya está completo.

## Arrancar o actualizar tras integrar un módulo

Desde la raíz del repositorio, una vez realizado el merge de la rama del módulo:

```sh
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

Accesos:

- Frontend: http://localhost:5173
- API: http://localhost:8000/api/v1/
- Swagger: http://localhost:8000/api/docs/
- Catálogo público de planes: http://localhost:8000/api/v1/planes/

Los healthchecks comprueban que Vite responde y que la API puede consultar los planes en PostgreSQL. Un backend `unhealthy` requiere revisar conectividad/permisos de la base y configuración, no ejecutar migraciones. La salud de la API no certifica el acceso a S3 ni sustituye una prueba de transferencia.

Los bind mounts conservan el desarrollo en vivo; `:z` permite su uso compartido en hosts con SELinux. Las dependencias Python se actualizan con la reconstrucción de la imagen. El frontend compara `package-lock.json` con una marca dentro de su volumen `node_modules`: solo ejecuta `npm ci` cuando difieren o falta la marca. Así un volumen antiguo no oculta dependencias incorporadas por un módulo nuevo. No se elimina el volumen al actualizar.

`compose.yaml` es el archivo canónico. `composer.yaml` conserva el nombre histórico como alias mediante `include`, para evitar dos configuraciones divergentes.

## Pruebas reproducibles sin tocar la base externa

```sh
python -m unittest discover -s frontend/tests -v
docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from tests
docker compose -f compose.test.yaml down
docker compose run --rm --no-deps frontend npm run build
docker compose run --rm --no-deps frontend npm run lint
```

El proyecto `cloudvault-tests` usa PostgreSQL 16 en una red interna sin puertos publicados y con datos temporales en memoria. No carga `.env`, no usa credenciales reales y exige una base de pruebas distinta. Carga `database/schema_desplegado.sql` únicamente en esa base. La imagen contiene este archivo bajo `/database`, por lo que las pruebas no dependen de archivos personales o de un montaje del checkout.

Se ejecutan explícitamente `common`, `auth_workspaces`, `storage`, `subscriptions` y, con su configuración independiente, `almacenamiento.tests`. Esta última conserva sus rutas temporales heredadas dentro de un tmpfs del contenedor. No se descubre automáticamente `almacenamiento.tests_persistencia`, que exige su propio clúster/controlador y no es intercambiable con el runner principal. Estas suites no certifican transferencias reales a Railway S3.

## Diagnóstico y seguridad

```sh
docker compose logs --tail 80 backend frontend
docker compose exec backend python manage.py check
docker compose exec backend python manage.py inspeccionar_almacenamiento
docker compose exec backend sh almacenamiento/operacion/iniciar_mantenimiento.sh --comprobar
```

La inspección del almacenamiento es de solo lectura; la comprobación de mantenimiento valida la interfaz sin iniciar ciclos. El proceso de limpieza continua no se activa automáticamente: puede eliminar objetos técnicos y requiere autorización operativa expresa.

Los Dockerfiles excluyen `.env*`, cachés y archivos personales. El contexto del backend es la raíz del repositorio, limitado por `.dockerignore`; para construirlo sin Compose usar `docker build -f backend/Dockerfile -t cloudvault-backend:dev .`.

Si una descarga pública falla en el helper de credenciales GPG, no borrar ni modificar `~/.docker/config.json` o el almacén de contraseñas. Desbloquear el almacén o usar temporalmente un `DOCKER_CONFIG` vacío con el mismo endpoint del motor permite descargar imágenes públicas de forma anónima; ese entorno no sirve para registros privados.

Los Dockerfiles admiten `--build-arg PYTHON_BASE_IMAGE=...` y `--build-arg NODE_BASE_IMAGE=...` para reconstruir sobre una imagen local verificada cuando el registro está inaccesible. Sus valores predeterminados siguen siendo `python:3.12-slim` y `node:22-bookworm-slim`. Si se reutiliza una imagen anterior de la aplicación como base, respaldar primero su etiqueta y verificar intérpretes/dependencias; las instrucciones de instalación de requirements/lockfile y copia del código nuevo siguen ejecutándose. Es una alternativa puntual, no una actualización de las imágenes base del sistema.

`docker compose stop` detiene la aplicación conservando los contenedores; `docker compose down` elimina los contenedores de este proyecto y mantiene los volúmenes. No usar `down -v` ni `system prune` como método de actualización.
