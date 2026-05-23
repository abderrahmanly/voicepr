#!/usr/bin/env bash
# Run the backend locally (no Docker) using SQLite. Useful when Postgres
# isn't available. Run from the project root.

set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

# .env in backend/ already targets sqlite:///./voicepr.db
.venv/bin/python -m app.db.init_db
.venv/bin/python -m app.rag.bootstrap
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
