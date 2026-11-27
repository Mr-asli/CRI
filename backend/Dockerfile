FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . && mkdir -p /data && chown 65532:65532 /data

COPY cri ./cri
COPY alembic ./alembic

USER 65532:65532

EXPOSE 8000

CMD ["uvicorn", "cri.main:app", "--host", "0.0.0.0", "--port", "8000"]
