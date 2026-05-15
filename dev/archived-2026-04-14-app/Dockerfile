# Unified backend + frontend image for Railway (single service).
# Build context must be `dev/archived-2026-04-14-app/` so both backend/
# and frontend/ are reachable from this Dockerfile.

# =========================================
# Stage 1 — Frontend build (Node)
# =========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

# Empty default = same-origin API calls (since FastAPI serves the bundle).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# =========================================
# Stage 2 — Python dep install
# =========================================
FROM python:3.11-slim AS backend-builder
WORKDIR /build

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================
# Stage 3 — Runtime
# =========================================
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Python packages
COPY --from=backend-builder /install /usr/local

# Backend application code
COPY backend/ .

# Frontend static bundle
COPY --from=frontend-builder /frontend/dist ./static

RUN mkdir -p uploads && chmod +x entrypoint.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "300", "--graceful-timeout", "30"]
