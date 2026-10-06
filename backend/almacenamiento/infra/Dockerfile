FROM python:3.14.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Solo código necesario para pruebas. Nunca COPY . ni copiar .env.
COPY backend/almacenamiento /app/backend/almacenamiento
COPY backend/auth_workspaces /app/backend/auth_workspaces
COPY backend/config /app/backend/config
COPY agente/contrato-fase-01.openapi.json /app/agente/contrato-fase-01.openapi.json
RUN useradd --uid 10001 --create-home pruebas
USER pruebas
CMD ["python", "-m", "django", "test", "almacenamiento.tests", "auth_workspaces.tests.test_error_security", "--settings=almacenamiento.tests.settings", "--verbosity=1"]
