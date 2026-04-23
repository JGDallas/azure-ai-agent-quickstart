FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data \
    SAMPLE_DOCS_DIR=/app/sample_docs

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi==0.115.4" \
    "uvicorn[standard]==0.32.0" \
    "openai==1.54.3" \
    "azure-identity==1.19.0" \
    "azure-search-documents==11.5.2" \
    "azure-monitor-opentelemetry==1.6.4" \
    "httpx==0.27.2" \
    "pydantic==2.9.2" \
    "python-multipart==0.0.12" \
    "sse-starlette==2.1.3"

COPY app ./app
COPY sample_docs ./sample_docs

RUN mkdir -p /data

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
