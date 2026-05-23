"""Vapi webhook handlers.

Vapi sends two kinds of POST events to a single configured webhook URL:

  - `tool-calls`    — the LLM wants to invoke a tool we declared on the
                      assistant. We must respond with a `results` array,
                      each entry pairing a `toolCallId` with `result` text.

  - `end-of-call-report` — fired when a call hangs up. We persist it.

We accept the path `/vapi/webhook` for everything and dispatch on
`message.type`. The single-URL design keeps the Vapi-side config simple
and the ngrok tunnel narrow.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import CallLog
from app.db.session import get_db
from app.rag.store import get_store
from app.services import appointments as svc

log = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi"])


def _verify_secret(x_vapi_secret: str | None = Header(default=None)) -> None:
    """Optional shared-secret check. Configure the same value in Vapi headers."""
    expected = settings.vapi_webhook_secret
    if not expected:
        return  # secret not configured → skip check (useful for local dev)
    if x_vapi_secret != expected:
        raise HTTPException(status_code=401, detail="invalid webhook secret")


# ---------- tool handlers ------------------------------------------------

def _ok(message: str) -> str:
    return message


def _err(message: str) -> str:
    # Vapi will read this back to the caller, so phrase it naturally in Italian
    return f"Errore: {message}"


def handle_cerca_informazioni_servizio(args: dict, db: Session) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return _err("manca la domanda da cercare.")
    top_k = int(args.get("top_k") or 4)
    hits = get_store().search(query, top_k=top_k)
    if not hits:
        return (
            "Non ho trovato informazioni sull'argomento richiesto. "
            "Posso provare a riformulare la domanda?"
        )
    # Compact, plain-text payload — the LLM will read this back to the caller
    pieces = []
    for h in hits:
        pieces.append(f"• {h['title']}: {h['text']}")
        if h.get("url"):
            pieces.append(f"  Fonte: {h['url']}")
    return "\n".join(pieces)


def handle_lista_slot_disponibili(args: dict, db: Session) -> str:
    office = (args.get("office") or "").strip()
    date_str = (args.get("date") or "").strip()
    if not office or not date_str:
        return _err("servono sia l'ufficio che la data.")
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return _err(f"la data '{date_str}' non è valida. Usa il formato AAAA-MM-GG.")
    try:
        slots = svc.available_slots(db, office, target_date)
    except svc.BookingError as e:
        return _err(str(e))
    if not slots:
        return f"Per il {target_date.strftime('%d/%m/%Y')} non ci sono slot disponibili."
    # Limit verbose voice readback to 6 slots
    pretty = [s.strftime("%H:%M") for s in slots[:6]]
    suffix = "" if len(slots) <= 6 else f" (e altri {len(slots) - 6})"
    return (
        f"Per {svc.OFFICES[svc.normalize_office(office)]} "
        f"il {target_date.strftime('%d/%m/%Y')} sono disponibili: "
        f"{', '.join(pretty)}{suffix}."
    )


def handle_prenota_appuntamento(args: dict, db: Session) -> str:
    required = ["citizen_name", "office", "scheduled_at"]
    missing = [k for k in required if not (args.get(k) or "").strip()]
    if missing:
        return _err(f"mancano i campi: {', '.join(missing)}.")
    try:
        when = date_parser.parse(args["scheduled_at"])
    except (ValueError, TypeError):
        return _err(f"non riesco a interpretare la data '{args['scheduled_at']}'.")
    try:
        appt = svc.create_appointment(
            db,
            citizen_name=args["citizen_name"],
            office=args["office"],
            scheduled_at=when,
            fiscal_code=args.get("fiscal_code"),
            phone=args.get("phone"),
            reason=args.get("reason"),
        )
    except svc.BookingError as e:
        return _err(str(e))
    spelled_code = " ".join(appt.code)  # "A B 1 2 ..." reads more clearly aloud
    when_local = svc.to_rome(appt.scheduled_at)
    return (
        f"Appuntamento confermato per {appt.citizen_name} "
        f"presso {svc.OFFICES[appt.office]} "
        f"il {when_local.strftime('%d/%m/%Y')} alle {when_local.strftime('%H:%M')}. "
        f"Il codice di prenotazione è: {spelled_code}."
    )


def handle_verifica_appuntamento(args: dict, db: Session) -> str:
    code = (args.get("code") or "").strip()
    if not code:
        return _err("manca il codice prenotazione.")
    appt = svc.get_by_code(db, code)
    if not appt:
        return f"Non ho trovato nessun appuntamento con il codice {code}."
    when_local = svc.to_rome(appt.scheduled_at)
    return (
        f"Appuntamento trovato. Intestato a {appt.citizen_name}, "
        f"presso {svc.OFFICES[appt.office]}, "
        f"il {when_local.strftime('%d/%m/%Y')} alle {when_local.strftime('%H:%M')}. "
        f"Stato: {appt.status}."
    )


TOOL_HANDLERS = {
    "cerca_informazioni_servizio": handle_cerca_informazioni_servizio,
    "lista_slot_disponibili": handle_lista_slot_disponibili,
    "prenota_appuntamento": handle_prenota_appuntamento,
    "verifica_appuntamento": handle_verifica_appuntamento,
}


# ---------- webhook entrypoint -------------------------------------------

def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Vapi sends Unix ms timestamps for some fields
        return datetime.fromtimestamp(value / 1000)
    try:
        return date_parser.parse(str(value))
    except (ValueError, TypeError):
        return None


def _save_call_log(payload: dict, db: Session) -> None:
    call = payload.get("call") or {}
    call_id = call.get("id") or payload.get("callId") or f"unknown-{datetime.utcnow().isoformat()}"

    existing = db.query(CallLog).filter(CallLog.call_id == call_id).one_or_none()
    log_row = existing or CallLog(call_id=call_id)
    log_row.started_at = _parse_dt(call.get("startedAt") or payload.get("startedAt"))
    log_row.ended_at = _parse_dt(call.get("endedAt") or payload.get("endedAt"))
    log_row.ended_reason = payload.get("endedReason") or call.get("endedReason")
    log_row.summary = payload.get("summary") or payload.get("analysis", {}).get("summary")
    log_row.transcript = payload.get("transcript")
    log_row.recording_url = payload.get("recordingUrl") or payload.get("stereoRecordingUrl")
    log_row.raw = payload

    if not existing:
        db.add(log_row)
    db.commit()


@router.post("/webhook")
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
) -> dict:
    body = await request.json()
    message = body.get("message") or {}
    mtype = message.get("type")
    log.info("Vapi webhook received: type=%s", mtype)

    if mtype == "tool-calls":
        results = []
        tool_calls = message.get("toolCallList") or message.get("toolCalls") or []
        for call in tool_calls:
            tool_call_id = call.get("id") or call.get("toolCallId")
            fn = call.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or {}
            if isinstance(raw_args, str):
                # Older Vapi payloads stringify the args
                import json as _json
                try:
                    raw_args = _json.loads(raw_args)
                except _json.JSONDecodeError:
                    raw_args = {}
            handler = TOOL_HANDLERS.get(name)
            if not handler:
                result_text = _err(f"strumento sconosciuto: {name}")
            else:
                try:
                    result_text = handler(raw_args, db)
                except Exception as e:  # noqa: BLE001 — never crash the call
                    log.exception("Tool handler %s failed", name)
                    result_text = _err(f"errore tecnico nel tool {name}: {e}")
            results.append({"toolCallId": tool_call_id, "result": result_text})
        return {"results": results}

    if mtype == "end-of-call-report":
        _save_call_log(message, db)
        return {"status": "ok"}

    # status-update / speech-update / etc. — acknowledge but don't act
    return {"status": "ignored", "type": mtype}
