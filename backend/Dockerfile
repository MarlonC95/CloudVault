ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
# El runner SQL necesita la misma referencia que el módulo integrado.
COPY database/schema_desplegado.sql /database/schema_desplegado.sql

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]