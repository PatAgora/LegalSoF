# Unified backend + frontend image.
# Root Directory in Railway should be: dev/archived-2026-04-14-app/backend

# =========================================
# Stage 1 — Build the React frontend
# =========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# =========================================
# Stage 2 — Python deps
# =========================================
FROM python:3.11-slim AS backend-builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =========================================
# Stage 3 — Runtime image
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

# Python packages from builder stage
COPY --from=backend-builder /install /usr/local

# Backend source (everything in this dir except the frontend subtree)
COPY . .

# Built frontend bundle, dropped into /app/static so FastAPI can serve it
COPY --from=frontend-builder /frontend/dist ./static

# Remove the raw frontend source from the runtime image (we only need the build output)
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
