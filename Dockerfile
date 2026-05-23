# Root Dockerfile for Hugging Face Spaces (Docker SDK).
# Multi-stage: builds the React frontend, then ships it alongside the
# FastAPI backend in a single image. Frontend is served from /dashboard.
#
# Local docker-compose still uses backend/Dockerfile and frontend/Dockerfile
# as separate services.

# ─── Stage 1: build the frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
# Build with /dashboard/ as the base so assets resolve correctly, and
# empty VITE_API_BASE so fetches go to the same origin.
# Vapi credentials below are PUBLIC by design (the assistant ID is just
# an identifier, the public key is the client-side counterpart to the
# server-side private key) — safe to commit and ship to browsers.
ENV VITE_BASE_PATH=/dashboard/ \
    VITE_API_BASE= \
    VITE_VAPI_PUBLIC_KEY=e4313478-0071-4603-ab27-57990488fba5 \
    VITE_VAPI_ASSISTANT_ID=285517dc-4fe6-483c-b775-3439df7eccbe
RUN npm run build

# ─── Stage 2: backend image with bundled frontend ───────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ .

# Drop the built SPA where FastAPI's main.py expects it.
COPY --from=frontend-build /fe/dist /app/static/dashboard

# HF Spaces requires the writable path /data; mount HF cache + sqlite there.
RUN mkdir -p /data

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
