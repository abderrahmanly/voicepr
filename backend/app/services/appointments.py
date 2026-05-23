"""Appointment booking logic.

Office list and validation rules live here so they're easy to evolve.
"""

from __future__ import annotations

import secrets
import string
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Appointment

ROME = ZoneInfo("Europe/Rome")

# Offices the bot can book against. Keep aligned with the RAG service titles
# so the bot can suggest the right one from a citizen description.
OFFICES: dict[str, str] = {
    "anagrafe": "Ufficio Anagrafe",
    "stato_civile": "Ufficio Stato Civile",
    "tributi": "Ufficio Tributi",
    "ufficio_tecnico": "Ufficio Tecnico",
    "ufficio_elettorale": "Ufficio Elettorale",
    "protocollo": "Ufficio Protocollo",
    "servizi_sociali": "Servizi Sociali",
    "polizia_locale": "Polizia Locale",
    "scuola": "Ufficio Istruzione",
}


class BookingError(ValueError):
    """Raised when an appointment request cannot be honored."""


def normalize_office(office: str) -> str:
    """Map a free-form office name to a canonical key. Raises if unknown."""
    key = office.strip().lower().replace(" ", "_").replace("'", "")
    # Try exact match on key first
    if key in OFFICES:
        return key
    # Then fuzzy: substring match on the human label
    for canon, label in OFFICES.items():
        if key in label.lower().replace(" ", "_") or canon in key:
            return canon
    raise BookingError(
        f"Ufficio non riconosciuto: '{office}'. "
        f"Uffici disponibili: {', '.join(OFFICES.values())}."
    )


def _gen_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _ensure_business_time(dt: datetime) -> None:
    local = dt.astimezone(ROME)
    if local.weekday() >= 5:
        raise BookingError("Gli uffici sono chiusi nel weekend.")
    open_t = time(settings.appointment_open_hour, 0)
    close_t = time(settings.appointment_close_hour, 0)
    if not (open_t <= local.time() < close_t):
        raise BookingError(
            f"Gli uffici sono aperti dalle {open_t.strftime('%H:%M')} "
            f"alle {close_t.strftime('%H:%M')}."
        )
    minutes = local.minute
    if minutes % settings.appointment_slot_minutes != 0:
        raise BookingError(
            f"Gli appuntamenti partono ogni {settings.appointment_slot_minutes} minuti."
        )


def create_appointment(
    db: Session,
    *,
    citizen_name: str,
    office: str,
    scheduled_at: datetime,
    fiscal_code: str | None = None,
    phone: str | None = None,
    reason: str | None = None,
) -> Appointment:
    office_key = normalize_office(office)

    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=ROME)
    if scheduled_at <= datetime.now(timezone.utc):
        raise BookingError("Non posso prenotare un appuntamento nel passato.")
    _ensure_business_time(scheduled_at)

    # Reject double-booking of the same slot for the same office
    clash = db.scalar(
        select(Appointment).where(
            Appointment.office == office_key,
            Appointment.scheduled_at == scheduled_at,
            Appointment.status == "confirmed",
        )
    )
    if clash:
        raise BookingError(
            "Questo orario è già occupato. Vuoi che ti proponga uno slot vicino?"
        )

    # Generate a unique short code; retry on the (very unlikely) collision
    for _ in range(5):
        code = _gen_code()
        if not db.scalar(select(Appointment).where(Appointment.code == code)):
            break
    else:
        raise BookingError("Errore interno nel generare il codice prenotazione.")

    appt = Appointment(
        code=code,
        citizen_name=citizen_name.strip(),
        fiscal_code=(fiscal_code or "").strip().upper() or None,
        phone=(phone or "").strip() or None,
        office=office_key,
        reason=(reason or "").strip() or None,
        scheduled_at=scheduled_at,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


def to_rome(dt: datetime) -> datetime:
    """Treat a naive DB datetime as Rome wall-clock (SQLite strips tz).
    Pass through aware datetimes unchanged via astimezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ROME)
    return dt.astimezone(ROME)


def get_by_code(db: Session, code: str) -> Appointment | None:
    return db.scalar(select(Appointment).where(Appointment.code == code.upper().strip()))


def available_slots(db: Session, office: str, target_date: date) -> list[datetime]:
    office_key = normalize_office(office)
    if target_date.weekday() >= 5:
        return []

    start = datetime.combine(target_date, time(settings.appointment_open_hour, 0), tzinfo=ROME)
    end = datetime.combine(target_date, time(settings.appointment_close_hour, 0), tzinfo=ROME)
    step = timedelta(minutes=settings.appointment_slot_minutes)

    # Don't offer past slots for today
    now = datetime.now(ROME)
    cursor = max(start, now.replace(second=0, microsecond=0)) if target_date == now.date() else start

    candidates: list[datetime] = []
    while cursor < end:
        # Round forward to the next valid slot boundary
        rem = cursor.minute % settings.appointment_slot_minutes
        if rem != 0:
            cursor = cursor + timedelta(minutes=settings.appointment_slot_minutes - rem)
            cursor = cursor.replace(second=0, microsecond=0)
            continue
        candidates.append(cursor)
        cursor += step

    taken = {
        a.scheduled_at.astimezone(ROME)
        for a in db.scalars(
            select(Appointment).where(
                Appointment.office == office_key,
                Appointment.scheduled_at >= start,
                Appointment.scheduled_at < end,
                Appointment.status == "confirmed",
            )
        )
    }
    return [c for c in candidates if c not in taken]


def list_appointments(db: Session, limit: int = 100) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment).order_by(Appointment.scheduled_at.desc()).limit(limit)
        )
    )
