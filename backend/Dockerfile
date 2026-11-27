FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/cri ./cri
RUN pip install --no-cache-dir . && mkdir -p /data && chown 65532:65532 /data
COPY backend/alembic ./alembic
COPY backend/scripts ./scripts
USER 65532:65532
EXPOSE 8000
CMD ["sh", "-c", "set -e; if [ -n \"$CRI_MIGRATION_DATABASE_URL\" ]; then python scripts/migrate.py; unset CRI_MIGRATION_DATABASE_URL CRI_APP_PASSWORD; fi; exec uvicorn cri.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
