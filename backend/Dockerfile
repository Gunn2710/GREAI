# syntax=docker/dockerfile:1
# Backend API. Build context is the repository root (it needs engine/ too):
#   docker build -f backend/Dockerfile .

# --- Build stage: compile the C++ engine and collect wheels -------------------
FROM python:3.12-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt -c constraints.txt
COPY engine/ engine/
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels ./engine

# --- Runtime stage --------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
COPY --from=build /wheels /tmp/wheels
RUN pip install --no-cache-dir --no-index /tmp/wheels/* && rm -rf /tmp/wheels

WORKDIR /app
COPY --chown=app:app backend/ .
# The app user must be able to create files here (e.g. a SQLite database).
RUN chown app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
# One process: migrations run on startup and must not race each other.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
