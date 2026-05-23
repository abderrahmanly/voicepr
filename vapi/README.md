# Vapi assistant — setup

This folder contains everything needed to recreate the voicebot in your own Vapi account.

## Files

- `assistant.json` — full assistant configuration (model, voice, transcriber, tools, prompt).
- `prompt.md` — the Italian system prompt with annotations explaining each section.

## Quick setup

1. **Create a Vapi account** at https://vapi.ai (free trial credits cover the demo).

2. **Start the backend and expose it via ngrok** (see the root `README.md`):
   ```bash
   docker compose up -d
   ngrok http 8000
   ```
   Copy the HTTPS forwarding URL (e.g. `https://abc123.ngrok-free.app`).

3. **Choose your import path**:

   ### Option A — API import (fastest)
   ```bash
   export VAPI_API_KEY="your-private-api-key"
   export NGROK_URL="https://abc123.ngrok-free.app"
   export VAPI_SECRET="$(grep VAPI_WEBHOOK_SECRET ../.env | cut -d= -f2)"

   # substitute the placeholders in-place
   sed -e "s|REPLACE_WITH_NGROK_URL|$NGROK_URL|g" \
       -e "s|REPLACE_WITH_YOUR_VAPI_WEBHOOK_SECRET|$VAPI_SECRET|g" \
       assistant.json > /tmp/assistant.ready.json

   curl -X POST https://api.vapi.ai/assistant \
        -H "Authorization: Bearer $VAPI_API_KEY" \
        -H "Content-Type: application/json" \
        -d @/tmp/assistant.ready.json
   ```

   ### Option B — Dashboard
   1. Open https://dashboard.vapi.ai → **Assistants** → **Create Assistant** → **Blank Template**.
   2. **Model** tab: provider `OpenAI`, model `gpt-4o-mini`, temperature `0.3`.
      Paste the contents of `prompt.md` (from the `Sei l'assistente…` line onwards) into the **System Message**.
   3. **Voice** tab: provider `Azure`, voice `it-IT-IsabellaNeural`.
   4. **Transcriber** tab: provider `Deepgram`, model `nova-2`, language `Italian (it)`.
   5. **Tools** tab: add 4 server tools using the function schemas in `assistant.json`. For every tool, set the server URL to `https://YOUR-NGROK.ngrok-free.app/vapi/webhook`.
   6. **Advanced** tab: set the assistant-level **Server URL** to the same `/vapi/webhook` endpoint and add the header `X-Vapi-Secret: <your VAPI_WEBHOOK_SECRET from .env>`.
   7. **Messages**: server messages → check `tool-calls` and `end-of-call-report`.

4. **Test the call**: Use the **Talk to Assistant** button in the dashboard, or place a web call from the Vapi playground. Watch the backend logs (`docker compose logs -f backend`) — you should see `Vapi webhook received: type=tool-calls` when the bot retrieves info or books appointments.

## Free-provider rationale

All three providers below are billable, but Vapi's free trial credits cover them:

| Layer | Provider | Why |
|---|---|---|
| STT | Deepgram `nova-2` | Best free-tier Italian transcription with low latency; supports endpointing. |
| TTS | Azure `it-IT-IsabellaNeural` | Natural Italian neural voice, no extra setup on Vapi. |
| LLM | OpenAI `gpt-4o-mini` | Cheap, good IT, strong function-calling. Temperature 0.3 keeps responses grounded. |

If you prefer to avoid OpenAI you can switch to `google/gemini-1.5-flash` or `groq/llama-3.1-70b` — all are wired into Vapi and support function calling.

## Editing the prompt

Don't edit the JSON's system message by hand — it's an escaped one-liner. Edit `prompt.md`, then regenerate the JSON section with:

```bash
python3 -c "
import json, pathlib
prompt = pathlib.Path('prompt.md').read_text().split('---', 2)[2].strip()
cfg = json.loads(pathlib.Path('assistant.json').read_text())
cfg['model']['messages'][0]['content'] = prompt
pathlib.Path('assistant.json').write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
"
```
