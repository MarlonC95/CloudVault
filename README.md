# CloudVault
CloudVault es una plataforma web de almacenamiento como servicio (PaaS) que permite la gestión segura de archivos, control de acceso basado en roles (RBAC), enlaces temporales compartidos y papelera lógica con retención de 30 días. Desarrollada con React, Django REST Framework, PostgreSQL y almacenamiento desacoplado con URLs prefirmadas (S3/MinIO)

## Backend

Requiere Python 3.10+ y las dependencias de `backend/requirements.txt`.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

La API queda disponible en `http://127.0.0.1:8000/api/v1/`. Por defecto se usa
SQLite; para PostgreSQL exporta `DATABASE_URL=postgresql://usuario:clave@host:5432/cloudvault`.

### Pruebas

```bash
cd backend
python manage.py test
```
