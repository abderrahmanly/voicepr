# Root Dockerfile for Hugging Face Spaces (Docker SDK).
# HF Spaces require the Dockerfile at the repo root; this builds only
# the backend tree. Local docker-compose still uses backend/Dockerfile.

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

# HF Spaces requires the writable path /data; mount HF cache + sqlite there.
RUN mkdir -p /data

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
