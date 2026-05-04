# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────
# Stage 1: build the Svelte frontend with Vite.
# ──────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend

COPY frontend/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ──────────────────────────────────────────────────────────────────────
# Stage 2: Python backend that also serves the built SPA.
# ──────────────────────────────────────────────────────────────────────
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist /frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
