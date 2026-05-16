# Parent-level Dockerfile for Railway.
# Works whether Railway's Root Directory is `dev/archived-2026-04-14-app`
# (this file is picked up) or `dev/archived-2026-04-14-app/backend`
# (backend/Dockerfile is picked up). Both produce the same image.

# =========================================
# Stage 1 — React frontend build
# =========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY backend/frontend/package*.json ./
RUN npm ci

COPY backend/frontend/ ./
RUN npm run build

# =========================================
# Stage 2 — Python deps
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

COPY --from=backend-builder /install /usr/local
COPY backend/ .
COPY --from=frontend-builder /frontend/dist ./static

RUN rm -rf /app/frontend \
    && mkdir -p uploads \
    && chmod +x entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f "http://localhost:${PORT:-8000}/health" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["sh", "-c", "gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 300 --graceful-timeout 30"]
