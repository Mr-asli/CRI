FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir . && mkdir -p /data && chown 65532:65532 /data
COPY cri ./cri
USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "cri.main:app", "--host", "0.0.0.0", "--port", "8000"]
