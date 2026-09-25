# Backend de CloudVault

Hecho con Django y PostgreSQL. Actualmente permite registrar usuarios, iniciar sesión y recuperar la contraseña.

## Cómo está organizado

```text
backend/
├── config/                 Configuración general y rutas de la API.
├── auth_workspaces/        Módulo de usuarios y autenticación.
│   ├── models.py           Usuarios y registros de auditoría.
│   ├── serializers.py      Validación de los datos recibidos.
│   ├── services.py         Creación de cuentas.
│   ├── login.py            Inicio de sesión y emisión de tokens.
│   ├── recovery.py         Recuperación de contraseña.
│   ├── views.py / urls.py   Solicitudes y direcciones de la API.
│   ├── authentication.py   Comprobación de tokens.
│   ├── throttles.py        Límites de intentos.
│   ├── exceptions.py       Respuestas de error.
│   ├── migrations/         Historial de los modelos.
│   └── tests/              Pruebas del módulo.
├── manage.py               Comandos para ejecutar Django.
├── requirements.txt        Librerías necesarias.
└── .env.example            Plantilla de configuración.
```

## Ejecutarlo en tu computadora

Necesitas Python y una base PostgreSQL con las tablas del proyecto ya creadas. Si es una base nueva, solicita el esquema SQL al equipo: las tablas de usuarios y auditoría no se crean con `migrate`.

**1. Instala las librerías**, desde la carpeta principal del proyecto:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt "psycopg[binary]"
```

En Windows, activa el entorno con `.venv\Scripts\activate`.

**2. Configura `.env`.** Si todavía no existe, copia `.env.example` como `.env`. Completa:

- `DATABASE_URL`: conexión a PostgreSQL.
- `DJANGO_SECRET_KEY`: una clave privada propia. Puedes generarla con `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- `DJANGO_DEBUG=True`: únicamente para desarrollo local.

**3. Inicia el backend:**

```bash
python manage.py check
python manage.py runserver
```

Abre [la página de la API](http://127.0.0.1:8000/api/docs/). Para detenerlo, presiona `Ctrl+C`.

## Desplegarlo en Railway

1. Conecta el repositorio y establece **Root Directory** en `/backend`.
2. Configura estos comandos en el servicio:

   **Build Command:**
   ```bash
   pip install -r requirements.txt "psycopg[binary]" gunicorn
   ```

   **Start Command:**
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --forwarded-allow-ips="*"
   ```

   Este comando presupone que todo el tráfico llega mediante el proxy confiable de Railway, sin acceso directo a Gunicorn por TCP. `--forwarded-allow-ips="*"` permite reconocer HTTPS en ese entorno; si hay acceso directo, reemplaza `*` por las IP de los proxies confiables antes de usarlo. [Referencia de Gunicorn](https://docs.gunicorn.org/en/stable/settings.html#forwarded-allow-ips).

3. Genera un dominio público y completa las variables de Railway:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | Conexión a PostgreSQL con las tablas ya creadas. |
   | `DJANGO_SECRET_KEY` | Una clave privada, aleatoria y estable para ese despliegue. |
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_ALLOWED_HOSTS` | Dominio del backend, sin `https://`. |
   | `CORS_ALLOWED_ORIGINS` | Dirección del frontend, con `https://` y sin barra final. |

4. Despliega y comprueba `https://TU-DOMINIO/api/docs/` por HTTPS. Revisa también las [mejoras de seguridad pendientes](../docs/auditoria-seguridad-registro-login.md) antes de habilitar usuarios reales.

La configuración se guarda en las variables de Railway; el archivo `.env` no se sube al repositorio. Estos pasos siguen la [guía oficial de Django en Railway](https://docs.railway.com/guides/django) y su [configuración para proyectos con varias carpetas](https://docs.railway.com/deployments/monorepo).
