---
title: Voicepr — Comune di Codroipo
emoji: 🏛️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Voicepr — Voicebot per i servizi del Comune di Codroipo

> **Demo live**
> Backend deployato come Docker Space su Hugging Face:
> 🔗 [`https://abdouly-voicepr.hf.space`](https://abdouly-voicepr.hf.space)
> Health: <https://abdouly-voicepr.hf.space/health> · Swagger: <https://abdouly-voicepr.hf.space/docs>
> Un assistente Vapi precaricato punta a questo backend; per parlare con il bot in italiano basta aprire l'assistente in Vapi dashboard e cliccare *Talk to Assistant*. Vedi `vapi/README.md` per importarne una copia nel proprio account.

Prototipo di assistente vocale in italiano che:

1. Risponde alle domande dei cittadini sui servizi del Comune di Codroipo (RAG su contenuti del sito).
2. Simula la prenotazione di un appuntamento presso un ufficio comunale.

Il voicebot gira su [Vapi](https://vapi.ai) e chiama i tool di un backend FastAPI esposto via `ngrok`. Le prenotazioni sono persistite su PostgreSQL, le chiamate sono loggate e visibili in un piccolo pannello React.

```
[Cittadino] ─▶ [Vapi (STT · LLM · TTS)]  ─▶  ngrok  ─▶  FastAPI  ─┬─▶ ChromaDB (RAG)
                                                                    └─▶ PostgreSQL (appointments, call_logs)
                                                                                ▲
                                                                  React UI ─────┘
```

## Stack

| Layer | Choice | Why |
|---|---|---|
| Voicebot | Vapi | Soluzione richiesta dal brief, gestisce STT+LLM+TTS+tool-calling |
| STT | Deepgram nova-2 | Best free-tier per IT, latenza bassa |
| TTS | Azure `it-IT-IsabellaNeural` | Voce neurale naturale, gratuita su trial Vapi |
| LLM | OpenAI `gpt-4o-mini` | Function-calling forte, costo basso, italiano fluente |
| Backend | FastAPI + SQLAlchemy 2 | Async, schema validation, ottimo DX |
| DB | PostgreSQL 16 | Persistenza appuntamenti + call logs |
| RAG | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) + ChromaDB | Open-source, multilingue, gira in locale senza GPU |
| Frontend | React + Vite + TypeScript | Minimal, type-safe |
| Infra | Docker Compose | Tre servizi: `db`, `backend`, `frontend` |

## Deploy sul cloud (Hugging Face Spaces)

Il backend è interamente Docker-based; il `Dockerfile` alla radice e il frontmatter di questo `README.md` (`sdk: docker, app_port: 7860`) sono compatibili con HF Spaces. Per replicare il deploy:

1. Crea uno Space `Docker` su <https://huggingface.co/new-space>.
2. Aggiungi il remote HF e fai push del repo: `git push hf main`.
3. Nella sezione *Settings → Variables and secrets* dello Space imposta:
   - secret `VAPI_WEBHOOK_SECRET` (stringa casuale)
   - variable `CORS_ORIGINS` = `*` (o restringi al tuo frontend)
   - variable `DATABASE_URL` = `sqlite:////data/voicepr.db` (la cartella `/data` è persistente su HF)
4. Dopo il primo build (~3-5 min con torch + sentence-transformers), aggiorna l'URL dei tool e del webhook dell'assistente Vapi in `<your-space-url>/vapi/webhook`.

HF gira la nostra immagine su CPU basic con 16 GB RAM gratuiti — più che sufficiente per il modello multilingue.

## Setup rapido (Docker locale)

Requisiti: Docker + Docker Compose. Per la prova vocale serve anche `ngrok`.

```bash
git clone <repo>
cd voicepr
cp .env.example .env       # personalizza VAPI_WEBHOOK_SECRET
docker compose up --build  # primo avvio: ~3 min (scarica il modello embedding)
```

Servizi:
- **Backend**: http://localhost:8000 — Swagger su http://localhost:8000/docs
- **Frontend**: http://localhost:8080
- **PostgreSQL**: `localhost:5432`

All'avvio il backend:
1. Crea le tabelle (idempotente).
2. Indicizza `backend/data/services.json` in ChromaDB (idempotente — usa `VOICEPR_FORCE_REINDEX=1` per ricostruire).

Verifica:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"come rinnovare la carta di identità","top_k":3}'
```

## Esporre il backend a Vapi con ngrok

```bash
ngrok http 8000
# copia l'URL HTTPS, es. https://abc123.ngrok-free.app
```

## Configurare l'assistente Vapi

Tutta la configurazione è in [`vapi/`](vapi/). Due opzioni:

- **Veloce (API)** — sostituisci i placeholder in `vapi/assistant.json` e fai un `POST /assistant`. Istruzioni complete in [`vapi/README.md`](vapi/README.md).
- **Manuale (Dashboard)** — crea un Assistant, copia il system prompt da [`vapi/prompt.md`](vapi/prompt.md), aggiungi i 4 tool con le definizioni da `assistant.json`, punta tutti gli URL al tuo `<ngrok>/vapi/webhook`.

Quando tutto è pronto: usa **Talk to Assistant** sul dashboard Vapi per chiamare il bot da browser.

## I 4 tool del Vapi agent

Tutti puntano allo stesso webhook (`POST /vapi/webhook`); il dispatcher backend smista in base al nome:

| Tool | Funzione |
|---|---|
| `cerca_informazioni_servizio` | RAG retrieval su `backend/data/services.json`. |
| `lista_slot_disponibili` | Slot liberi per `(ufficio, data)`. |
| `prenota_appuntamento` | Crea una prenotazione e ritorna un codice 8-caratteri. |
| `verifica_appuntamento` | Recupera una prenotazione dal codice. |

Lo stesso webhook riceve anche `end-of-call-report` da Vapi e lo persiste su `call_logs`.

## Esempi di dialogo

> **Cittadino:** "Buongiorno, vorrei sapere come si rinnova la carta di identità."
> **Bot:** *(chiama `cerca_informazioni_servizio` con `"rinnovo carta identità"`)*
> "Per rinnovare la carta d'identità deve fissare un appuntamento all'ufficio anagrafe. Le servono la vecchia carta o un altro documento, una fototessera recente e il codice fiscale. Il costo è di 22 euro e 21 centesimi. Vuole che le prenoti un appuntamento?"

> **Cittadino:** "Sì, martedì prossimo se possibile."
> **Bot:** "Martedì 26 maggio. Le va bene la mattina, ad esempio alle 10:00?"
> *(chiama `lista_slot_disponibili` con `office="anagrafe", date="2026-05-26"`)*
> *(dopo aver raccolto nome + codice fiscale)*
> "Riepilogo: appuntamento all'Ufficio Anagrafe martedì 26 maggio alle 10:00 per Mario Rossi, codice fiscale RSSMRA80A01H501Z, per il rinnovo della CIE. Confermo?"
> *(chiama `prenota_appuntamento`)*
> "Confermato. Il codice è: K — 7 — A — 2 — 9 — P — Q — 4. Lo conservi e porti con sé un documento d'identità."

## Struttura del repo

```
voicepr/
├── backend/                FastAPI app
│   ├── app/
│   │   ├── api/            routers: appointments, rag, calls, vapi
│   │   ├── core/           config (pydantic-settings)
│   │   ├── db/             SQLAlchemy models + session
│   │   ├── rag/            ChromaDB store + bootstrap
│   │   └── services/       business logic (appointments)
│   ├── scripts/
│   │   └── scrape_codroipo.py
│   └── data/
│       ├── services.baseline.json  (curato, sempre presente)
│       └── services.json           (rigenerato dallo scraper)
├── frontend/               React + Vite UI
├── vapi/                   assistant.json + prompt.md
├── docker-compose.yml
└── docs/                   NOTES, scelte, prossimi passi
```

## RAG: come funziona

1. Lo scraper prende il sitemap di `comune.codroipo.ud.it`, filtra le pagine "servizi" e prova due strategie (HTTP + Playwright opzionale).
2. Il dataset di partenza — `backend/data/services.baseline.json` — è curato a mano con 14 servizi reali (anagrafe, CIE, residenza, TARI, IMU, stato civile, ecc.) e funge da fallback robusto. Vedi [`docs/NOTES.md`](docs/NOTES.md) per il perché.
3. `app/rag/store.py` carica il modello multilingue `paraphrase-multilingual-MiniLM-L12-v2` (~120 MB, una volta sola), chunkizza ogni servizio (~500 caratteri, overlap 80), embedda e salva in una collection ChromaDB persistente su disco.
4. La similarity search usa cosine distance; al tool `cerca_informazioni_servizio` torna i top-K chunk con titolo + URL sorgente.

Rigenerare l'indice:

```bash
docker compose exec backend python -m app.rag.bootstrap
# oppure forzare un reset
docker compose exec -e VOICEPR_FORCE_REINDEX=1 backend python -m app.rag.bootstrap
```

## Sviluppo locale (senza Docker)

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://voicepr:voicepr@localhost:5432/voicepr"
python -m app.db.init_db
python -m app.rag.bootstrap
uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev    # http://localhost:5173
```

## Note finali

- Vedi [`docs/NOTES.md`](docs/NOTES.md) per le **scelte di design**, **limitazioni note** e **cosa farei con più tempo**.
- Strumenti AI usati durante lo sviluppo: dichiarati in `docs/NOTES.md`.
