---
title: Voicepr — Comune di Codroipo
emoji: 🏛️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Voicepr — Voicebot for the municipal services of Codroipo

> **Live demo (Hugging Face Spaces, Docker SDK)**
>
> | | |
> |---|---|
> | 🎛 Dashboard (appointments + call logs) — has a built-in "Talk to the assistant" button | https://abdouly-voicepr.hf.space/dashboard |
> | 📚 API docs (Swagger) | https://abdouly-voicepr.hf.space/docs |
> | ❤ Health check | https://abdouly-voicepr.hf.space/health |
>
> A Vapi assistant (`gpt-4o` + Deepgram IT + Azure `IsabellaNeural`) is already pointed at this backend. To talk to the bot in Italian: open the dashboard URL and click **Parla con l'assistente** — no Vapi account or signup needed, just a browser mic permission prompt. Instructions to import a copy of the assistant into your own Vapi account are in [`vapi/README.md`](vapi/README.md).
>
> _Note: Hugging Face puts the Space to sleep after 48 h of inactivity. The first request after sleep takes ~30 s to wake the container (the dashboard pre-warms by pinging `/health` on load)._

Italian-speaking voice assistant prototype that:

1. Answers citizens' questions about the municipal services of Codroipo (RAG over scraped/curated content).
2. Simulates booking an appointment at a municipal office.

The voicebot runs on [Vapi](https://vapi.ai) and calls tools exposed by a FastAPI backend reached via ngrok (locally) or Hugging Face Spaces (cloud). Appointments are persisted to PostgreSQL (Docker setup) or SQLite (local + HF setup); calls are logged and shown in a small React dashboard.

```
[Citizen] ─▶ [Vapi (STT · LLM · TTS)]  ─▶  HTTPS  ─▶  FastAPI  ─┬─▶ in-memory vector store (RAG)
                                                                  └─▶ PostgreSQL / SQLite (appointments, call_logs)
                                                                                ▲
                                                                  React UI ─────┘
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| Voicebot | Vapi | Required by the brief; handles STT + LLM + TTS + tool-calling in one place |
| STT | Deepgram nova-2 | Best free-tier Italian transcription with low latency |
| TTS | Azure `it-IT-IsabellaNeural` | Natural Italian neural voice, free on Vapi trial |
| LLM | OpenAI `gpt-4o` (`gpt-4o-mini` works too) | Strong function-calling, fluent Italian, handles relative dates |
| Backend | FastAPI + SQLAlchemy 2 | Async, schema validation, great DX |
| DB | PostgreSQL 16 (Docker) / SQLite (local + HF) | Persistence for appointments and call logs |
| RAG | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` + NumPy cosine | Open-source, multilingual, no GPU required |
| Frontend | React + Vite + TypeScript | Minimal, type-safe |
| Infra | Docker Compose (local) / HF Spaces (cloud) | Three services locally: db, backend, frontend |

## Deploy to the cloud (Hugging Face Spaces)

The backend is fully Docker-based. The root `Dockerfile` and this README's frontmatter (`sdk: docker`, `app_port: 7860`) are HF Spaces–compatible. To replicate the deploy:

1. Create a `Docker` Space at <https://huggingface.co/new-space>.
2. Add the HF remote and push: `git push hf main`.
3. In the Space's *Settings → Variables and secrets* tab set:
   - secret `VAPI_WEBHOOK_SECRET` (any strong random string)
   - variable `CORS_ORIGINS` = `*` (or restrict to your frontend origin)
   - variable `DATABASE_URL` = `sqlite:////data/voicepr.db` (the `/data` folder is persistent on HF)
4. After the first build (~3–5 min for torch + sentence-transformers), update the Vapi assistant's `server.url` and every tool's `server.url` to `https://<your-space>.hf.space/vapi/webhook`.

HF runs the image on a free CPU-basic instance with 16 GB RAM — plenty for the multilingual embedding model.

## Quick local setup (Docker Compose)

Requirements: Docker + Docker Compose. To exercise the voice path you also need `ngrok` (so Vapi can reach your local backend).

```bash
git clone <repo>
cd voicepr
cp .env.example .env       # customize VAPI_WEBHOOK_SECRET
docker compose up --build  # first boot ~3 min (downloads the embedding model)
```

Services:
- **Backend**: http://localhost:8000 — Swagger on http://localhost:8000/docs
- **Frontend**: http://localhost:8080
- **PostgreSQL**: `localhost:5432`

On startup the backend:
1. Creates the tables (idempotent).
2. Builds the in-memory RAG index from `backend/data/services.json` (rebuilt on every process start; takes ~5 s).

Verify:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"how to renew an ID card","top_k":3}'
```

## Exposing the local backend to Vapi via ngrok

```bash
ngrok http 8000
# copy the HTTPS URL, e.g. https://abc123.ngrok-free.app
```

## Configuring the Vapi assistant

All configuration lives in [`vapi/`](vapi/). Two options:

- **Fast (API)** — substitute the placeholders in `vapi/assistant.json` and `POST /assistant`. Full instructions in [`vapi/README.md`](vapi/README.md).
- **Manual (Dashboard)** — create an Assistant, paste the system prompt from [`vapi/prompt.md`](vapi/prompt.md), add the 4 tools using the schemas in `assistant.json`, point every URL at `<your-tunnel>/vapi/webhook`.

When everything is wired: open the assistant in the Vapi dashboard and click **Talk to Assistant** to make a browser-based voice call.

## The four Vapi tools

All tools point to the same webhook (`POST /vapi/webhook`); the backend dispatcher routes by tool name:

| Tool | Function |
|---|---|
| `cerca_informazioni_servizio` | RAG retrieval over `backend/data/services.json`. |
| `lista_slot_disponibili` | Free slots for `(office, date)`. |
| `prenota_appuntamento` | Creates a booking and returns an 8-character confirmation code. |
| `verifica_appuntamento` | Looks up an existing booking by code. |

The same webhook also receives `end-of-call-report` events from Vapi and persists them to `call_logs`.

## Example dialog

> **Citizen:** "Good morning, how do I renew my ID card?"
> **Bot:** *(calls `cerca_informazioni_servizio` with `"renew ID card"`)*
> "To renew your ID card you need to book an appointment at the Anagrafe office. You'll need the old card or another valid ID, a recent passport photo, and your tax code. The cost is 22 euros and 21 cents. Shall I book the appointment for you?"

> **Citizen:** "Yes please, next Tuesday if possible."
> **Bot:** "That would be Tuesday May 26th. Does the morning work, say 10:00?"
> *(calls `lista_slot_disponibili` with `office="anagrafe", date="2026-05-26"`)*
> *(after collecting name and tax code)*
> "Summary: appointment at the Anagrafe office on Tuesday May 26 at 10:00 for Mario Rossi, tax code RSSMRA80A01H501Z, to renew the ID card. Confirm?"
> *(calls `prenota_appuntamento`)*
> "Confirmed. Your code is: K — 7 — A — 2 — 9 — P — Q — 4. Please keep it and bring a valid ID."

## Repository layout

```
voicepr/
├── backend/                FastAPI app
│   ├── app/
│   │   ├── api/            routers: appointments, rag, calls, vapi
│   │   ├── core/           config (pydantic-settings)
│   │   ├── db/             SQLAlchemy models + session
│   │   ├── rag/            in-memory vector store + bootstrap
│   │   └── services/       business logic (appointments)
│   ├── scripts/
│   │   └── scrape_codroipo.py
│   └── data/
│       ├── services.baseline.json  (curated, always present)
│       ├── services.json           (overwritten by the scraper)
│       └── audio/                  (static ambient audio for Vapi)
├── frontend/               React + Vite UI
├── vapi/                   assistant.json + prompt.md
├── Dockerfile              Multi-stage image for HF Spaces (frontend + backend)
├── docker-compose.yml      Local 3-service orchestration (db, backend, frontend)
└── docs/                   Notes on choices, limitations, next steps
```

## How RAG works

1. The scraper pulls `comune.codroipo.ud.it`'s sitemap, filters service pages, and tries two strategies (HTTP + optional Playwright).
2. The seed dataset — `backend/data/services.baseline.json` — is hand-curated and contains 14 real Codroipo services (Anagrafe, CIE, residence, IMU, TARI, civil status, etc.); it acts as a robust fallback. See [`docs/NOTES.md`](docs/NOTES.md) for the rationale.
3. `app/rag/store.py` loads the multilingual model `paraphrase-multilingual-MiniLM-L12-v2` (~120 MB, once), chunks every service (~500 chars, 80-char overlap), embeds, and keeps the result in a NumPy matrix.
4. Similarity search uses cosine on L2-normalized vectors; the `cerca_informazioni_servizio` tool returns the top-K chunks with title + source URL.

Rebuild the index (when services.json changes):

```bash
docker compose exec backend python -m app.rag.bootstrap
```

## Local dev without Docker

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./voicepr.db"
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev    # http://localhost:5173
```

## Closing notes

- See [`docs/NOTES.md`](docs/NOTES.md) for **design choices**, **known limitations** and **what I would improve given more time**.
- AI tooling used during development is disclosed in `docs/NOTES.md` as required by the brief.
