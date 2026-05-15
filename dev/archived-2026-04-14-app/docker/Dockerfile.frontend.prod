# Production Dockerfile for Railway / any single-container PaaS.
# The original Dockerfile.frontend runs `npm run dev` for local docker-compose;
# this one does a real production build and serves the static bundle.

FROM node:20-alpine AS builder
WORKDIR /app

# VITE_* env vars are baked into the bundle at build time.
# Pass these as Railway build args (Service -> Variables -> "Build" tab).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Runtime stage — small static-file server
FROM node:20-alpine
WORKDIR /app

RUN addgroup -g 1001 -S appgroup && adduser -u 1001 -S appuser -G appgroup \
    && npm install -g serve@14

COPY --from=builder /app/dist ./dist

USER appuser

# Railway injects $PORT at runtime
ENV PORT=4173
EXPOSE 4173

CMD ["sh", "-c", "serve -s dist -l tcp://0.0.0.0:$PORT"]
