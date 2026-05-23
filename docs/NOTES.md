# Design notes, limitations and next steps

## Key choices (and the reasoning)

### A single webhook (`/vapi/webhook`) for all tools
Vapi supports both per-tool URLs and an assistant-level URL. I went with a **single endpoint** with internal dispatch in order to:
- minimize the surface exposed through ngrok (only one path to authorize);
- receive `end-of-call-report` and `tool-calls` on the same handler, which simplifies secret rotation;
- keep the system prompt shorter (no need to repeat the URL per tool).

The trade-off is that `app/api/vapi.py` carries more responsibility. I mitigated it by isolating each handler in its own function and mapping them in `TOOL_HANDLERS`.

### LLM model: `gpt-4o-mini` first, then `gpt-4o`
With temperature `0.3`, `gpt-4o-mini` is enough to:
- call tools at the right time;
- avoid hallucinations when the RAG returns no hit;
- resolve relative dates ("next Tuesday").

After the first test calls I bumped to `gpt-4o`: it parses messy date input ("the 26 05 at 4") more reliably and is noticeably better at reading numbers as natural Italian phrases instead of digit strings. For a production deployment with high call volume the mini variant + a slightly stricter prompt would be enough.

### Multilingual embeddings instead of an Italian-only model
`paraphrase-multilingual-MiniLM-L12-v2` is cross-lingual: the query "documenti per residenza" and the chunk "necessary documents for change of residence" still land close in vector space. For an app that may add Slovenian, Friulan, or tourist English in the future, this beats a monolingual Italian model.

### Curated `services.baseline.json` + best-effort scraper
The Codroipo site is an Angular SPA served by the regional CMS `backoffice-comuni.regione.fvg.it`. API responses return 401 without an authenticated session and the content is rendered client-side, so `curl` always gets the empty shell. The options were:

1. **Run Playwright in production** — works but adds ~1 GB to the Docker image and an inherently fragile dependency.
2. **Reverse-engineer the auth session** — fragile and likely against ToS.
3. **Hand-curate a dataset** + keep the scraper as a future upgrade.

I chose (3) because the brief explicitly allows hardcoded content ("If hardware limitations apply, it is acceptable to pass hardcoded content to the AI"). The side benefit is that the bot **always** answers with correct information even if the site changes structure tomorrow.

`scripts/scrape_codroipo.py` still works: it first tries `httpx` on the meta tags, then optionally Playwright (`--with-playwright`), and merges results non-destructively over the baseline (curation always wins on conflicts).

### Server-side validation, not prompt-only
Even though the prompt instructs the model not to book outside business hours, **I do not trust the prompt**. All validation (weekend, out-of-hours, slot collision, optional fiscal code, datetime in the past) lives in `app/services/appointments.py`. If the model tries to force a bad value, the tool returns a natural-Italian error message that the model can read back to the caller.

### Booking codes that read well over voice
8 characters (uppercase letters + digits) generated with `secrets.choice`. In the tool return text I space-out the characters (`" ".join(code)`) so the TTS pronounces them one at a time. A small trick, but it noticeably improves comprehension over the phone.

### CORS open only to configured origins
`CORS_ORIGINS` in `.env` controls the list; the default includes 5173 (dev) and 8080 (compose). In production you would tighten this further.

### In-memory RAG instead of ChromaDB
I started with `chromadb` for persistence but Python 3.14 has no wheels for the modern `chromadb` API yet (the only one that installs is a 2-year-old release). Rather than write a compat layer, I replaced the vector store with a small NumPy-backed in-memory index (~120 lines, same public interface). For a 14-service dataset this is faster than Chroma anyway. The interface is small enough to swap back to a persistent vector DB without touching anything outside `app/rag/store.py`.

### SQLite timezone glitch
Caught while running the smoke tests: SQLite strips timezone info on store, so reading the value back as a naive datetime and calling `.astimezone(ROME)` interprets it as machine-local time and shifts the displayed hour. Fixed with a small `to_rome()` helper that reattaches the Rome zone on naive datetimes. PostgreSQL (the production target) doesn't have this issue.

## Known limitations

1. **Live scraping is disabled by default.** The indexed dataset is 14 curated entries. Consistent with the brief, but the bot doesn't know about services outside that list (e.g. culture, sport, ZTL).
2. **Webhook secret is optional.** If `VAPI_WEBHOOK_SECRET` is empty the check is skipped — useful for local dev, must be set in any real deployment.
3. **No assistant-side timezone handling.** The backend normalizes everything to `Europe/Rome`, but if the model produces an ISO timestamp without offset it's assumed to be Rome. Edge case: citizens calling from abroad (irrelevant for this use case).
4. **No rate limit or auth on the REST endpoints.** `/appointments` is fully open: fine for a prototype, obviously not for production.
5. **Slot uniqueness is enforced application-side only.** The check is a SELECT-then-INSERT pattern: a true race between two concurrent calls could theoretically pass both. A database-level `UNIQUE(office, scheduled_at) WHERE status='confirmed'` would close it.
6. **No automated tests yet.** I would have added pytest + an httpx async client covering (a) booking validation, (b) the Vapi dispatcher, (c) the RAG chunker. See "What I'd improve" below.

## What I'd improve with more time

In order of impact:

1. **Test suite.** Pytest with an in-memory SQLite DB; mocks for Vapi `tool-calls` and `end-of-call-report`; an end-to-end smoke test against an ngrok-like fixture.
2. **Production scraping via a Playwright sidecar.** A separate container running on a cron schedule, writing to `data/services.json`, and asking the backend to re-index. Keeps the main image lean.
3. **Real calendar integration.** Replace the mocked availability with Google Calendar / Microsoft 365 per office. The `lista_slot_disponibili` tool interface doesn't need to change.
4. **SMS/email confirmation.** On successful `prenota_appuntamento`, send the code + an ICS link to the citizen.
5. **RAG eval set.** 30–50 synthetic questions → ground-truth chunks → measure recall@K. Without it, every chunker tweak is a guess.
6. **Analytics funnel.** The Chiamate dashboard currently shows raw logs; I would add call-success rate, average time-to-booking, tool-call frequency, drop-off rate.
7. **Auth on the REST endpoints + multi-tenant.** If the bot served multiple municipalities, partition by `tenant_id` and gate the admin endpoints.
8. **PII-safe transcripts.** Detect card numbers / tax codes in the transcript and mask them before persistence (Vapi supports PII patterns natively).
9. **Human handoff.** A `trasferisci_operatore` tool that routes to a real number when the citizen explicitly asks for a human — Vapi supports this via `transferCall`.
10. **Observability.** OpenTelemetry on FastAPI exported to Grafana Tempo for end-to-end latency debugging.

## AI tools used during development

- **Generic LLM assistant** — used for: initial exploration of the Codroipo site structure (realizing it's an Angular SPA on the regional KPAX CMS), brainstorming the stack choices, generating FastAPI/React boilerplate, reviewing the Italian system prompt for fluency.
- **IDE autocomplete** — on utility functions (chunker, date formatters) and repetitive snippets.

Nothing was committed without review. The information in `services.baseline.json` reflects standard Italian municipal practice for civil-registry / tax services and should be verified against the official site before any operational use.
