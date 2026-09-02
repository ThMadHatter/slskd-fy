# Stage 1: Build Next.js frontend static export
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy package descriptors first to leverage Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies deterministically
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build static Next.js export to /frontend/out
RUN npm run build

# Validate that frontend export artifacts were produced successfully
RUN test -f /frontend/out/index.html && test -d /frontend/out/_next || \
    (echo "ERROR: Next.js frontend build failed to produce /frontend/out/index.html or /frontend/out/_next" && exit 1)

# Stage 2: Install Python dependencies
FROM python:3.12-slim AS python-builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 3: Final lightweight runtime container without Node.js or npm
FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from python-builder
COPY --from=python-builder /root/.local /root/.local

# Copy backend application files
COPY app/ /app/app/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini

# Copy compiled frontend artifacts from frontend-builder into FastAPI template and static directories
COPY --from=frontend-builder /frontend/out/index.html /app/app/templates/index.html
COPY --from=frontend-builder /frontend/out/_next /app/app/static/_next

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app

# Dynamic Build Information Arguments (Injected at Docker build-time)
ARG APP_VERSION=0.4.7
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

ENV APP_VERSION=$APP_VERSION
ENV GIT_COMMIT=$GIT_COMMIT
ENV BUILD_DATE=$BUILD_DATE

EXPOSE 8000

# Container healthcheck using standard URL
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
