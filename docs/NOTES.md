# Note di progettazione, limitazioni e prossimi passi

## Scelte principali (e il perché)

### Un solo webhook (`/vapi/webhook`) per tutti i tool
La documentazione Vapi permette sia un URL per tool sia un URL unico a livello assistente. Ho scelto **un solo URL** con dispatch interno per:
- minimizzare la superficie esposta tramite ngrok (un solo path da autorizzare),
- ricevere `end-of-call-report` e `tool-calls` sullo stesso endpoint, semplificando la rotazione del secret,
- tenere il prompt più leggero (non serve un URL per tool nel system message).

Il rovescio della medaglia è che `app/api/vapi.py` ha più responsabilità: l'ho mitigato spostando ogni handler in una funzione separata e mappandoli in `TOOL_HANDLERS`.

### Modello LLM: `gpt-4o-mini`, non `gpt-4o`
A 0.3 di temperature il mini è sufficiente per:
- chiamare i tool al momento giusto,
- non inventare informazioni quando il RAG è vuoto,
- gestire le date relative ("martedì prossimo").

L'upgrade a `gpt-4o` migliorerebbe la robustezza su casi limite (dialoghi lunghi, ambiguità sui nomi propri) ma triplica il costo per minuto.

### Embedding multilingue e non solo italiano
`paraphrase-multilingual-MiniLM-L12-v2` è cross-lingua: la query "documenti per residenza" e il chunk con "necessary documents for change of residence" si avvicinerebbero in spazio. Per un'app che potrebbe domani aggiungere lingue (sloveno, friulano, inglese turisti), questo è meglio di un modello solo-italiano.

### `services.baseline.json` curato + scraper "best-effort"
Il sito di Codroipo è una SPA Angular alimentata dalla CMS regionale `backoffice-comuni.regione.fvg.it`. Le risposte API sono 401 senza una sessione autenticata; il rendering dei contenuti avviene client-side, quindi `curl` torna sempre lo shell vuoto. Le opzioni erano:

1. **Playwright in produzione** — funziona ma aggiunge ~1 GB all'immagine Docker e una dipendenza fragile.
2. **Reverse-engineering della sessione auth** — fragile e probabilmente vietato dai ToS.
3. **Dataset curato a mano** + scraper come futuro upgrade.

Ho scelto (3) perché il brief consente esplicitamente contenuti hardcoded ("If hardware limitations apply, it is acceptable to pass hardcoded content to the AI"). Il vantaggio collaterale è che il bot risponde **sempre** con informazioni corrette, anche se domani il sito cambia struttura.

`scripts/scrape_codroipo.py` resta funzionante: prova prima `httpx` sui meta-tag, poi opzionalmente Playwright (`--with-playwright`), e fa **merge non-distruttivo** sul baseline (la curatela vince in caso di conflitto).

### Validazione lato server, non solo nel prompt
Anche se il prompt istruisce il modello a non prenotare nei weekend, **non mi fido del prompt**. Tutta la validazione (weekend, fuori orario, slot occupato, codice fiscale opzionale, data nel passato) vive in `app/services/appointments.py`. Se il modello prova a forzare, il tool risponde con un messaggio d'errore in italiano che il modello sa rileggere al cittadino.

### Codici di prenotazione "leggibili a voce"
Codice di 8 caratteri (lettere maiuscole + cifre) generato con `secrets.choice`. Nel return text per il tool faccio uno **space-out** (`" ".join(code)`) per forzare il TTS a scandirli uno alla volta. È un trucco semplice ma sensibilmente migliora la comprensione al telefono.

### CORS aperto solo sugli host configurati
`CORS_ORIGINS` nel `.env` controlla la lista; default include 5173 (dev) e 8080 (compose). In produzione si stringerebbe ulteriormente.

## Limitazioni note

1. **Scraping live disabilitato di default**. Il dataset RAG è di 14 voci curate. È coerente con il brief, ma il bot non sa di servizi non inclusi (es. cultura, sport, ZTL).
2. **Webhook secret è opzionale**. Se `VAPI_WEBHOOK_SECRET` è vuoto, il check viene saltato — comodo in dev, da impostare in qualsiasi deploy reale.
3. **Nessuna gestione del fuso orario lato Vapi**. Il backend converte tutto in `Europe/Rome` ma se il modello produce un ISO senza offset, viene assunto Roma. Caso limite: cittadini all'estero (ininfluente per il caso d'uso).
4. **Nessun rate limit né auth sulle REST**. Le `/appointments` sono accessibili senza autenticazione: ok per un prototipo, ovviamente non per produzione.
5. **Nessun test automatico**. Avrei aggiunto pytest + httpx async client per coprire (a) la validazione delle prenotazioni, (b) il dispatcher Vapi, (c) il chunker RAG. Vedi sotto.

## Cosa farei con più tempo

In ordine d'impatto:

1. **Test suite**. Pytest con DB SQLite in-memory; mock di Vapi su `tool-calls` e `end-of-call-report`; smoke test contro un `ngrok`-like fixture.
2. **Scraping produttivo via Playwright sidecar**. Container separato che gira ogni 24h con cron, scrive su `data/services.json`, segnala a backend di reindicizzare. Mantiene l'immagine principale snella.
3. **Integrazione calendario reale**. Sostituire la disponibilità mock con Google Calendar / Microsoft 365 per office. Tool `lista_slot_disponibili` può rimanere uguale.
4. **Conferma via SMS/email**. All'`prenota_appuntamento` successo, inviare conferma con codice + ICS link.
5. **Eval set per il RAG**. 30-50 domande sintetiche → ground-truth chunk → misura recall@K. Senza questo, ogni tweak al chunking è una scommessa.
6. **Funnel analitico**. Dashboard "Chiamate" attualmente mostra solo i log grezzi; aggiungerei call-success rate, tempo medio per prenotazione, tool più chiamati, drop-off rate.
7. **Auth sulle REST + multi-tenant**. Se il bot servisse più comuni, separare per `tenant_id` e gate sulle API admin.
8. **Sicurezza voce**: rilevare numeri di carta nei transcript e mascherarli prima della persistenza (Vapi lo supporta nativamente con `pii` patterns).
9. **Fallback umano**. Tool `trasferisci_operatore` che instrada a un numero reale se il cittadino dice "voglio parlare con una persona" — Vapi supporta `transferCall`.
10. **Tracing**. OpenTelemetry su FastAPI + esportazione su Grafana Tempo per debug latenza end-to-end.

## Strumenti AI usati durante lo sviluppo

- **Assistente LLM generico** — usato come supporto su: esplorazione iniziale della struttura del sito di Codroipo (capire che è una SPA Angular alimentata dalla CMS regionale KPAX), brainstorming sulle scelte di stack, generazione di boilerplate FastAPI/React, revisione della fluidità del system prompt italiano.
- **Autocomplete IDE** — su funzioni utility (chunker, formatter date) e snippet ripetitivi.

Nessun contenuto è stato accettato senza revisione. Le informazioni nei `services.baseline.json` sono basate su pratiche standard italiane per i servizi anagrafici/tributari e andrebbero verificate puntualmente contro il sito ufficiale prima di un uso operativo.
