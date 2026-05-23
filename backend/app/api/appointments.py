"""Direct REST routes used by the frontend (not by Vapi)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import AppointmentCreate, AppointmentOut, SlotsOut
from app.db.session import get_db
from app.services import appointments as svc

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
def list_all(db: Session = Depends(get_db)) -> list[AppointmentOut]:
    return [AppointmentOut.model_validate(a) for a in svc.list_appointments(db)]


@router.post("", response_model=AppointmentOut, status_code=201)
def create(body: AppointmentCreate, db: Session = Depends(get_db)) -> AppointmentOut:
    try:
        appt = svc.create_appointment(
            db,
            citizen_name=body.citizen_name,
            office=body.office,
            scheduled_at=body.scheduled_at,
            fiscal_code=body.fiscal_code,
            phone=body.phone,
            reason=body.reason,
        )
    except svc.BookingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AppointmentOut.model_validate(appt)


@router.get("/{code}", response_model=AppointmentOut)
def get_one(code: str, db: Session = Depends(get_db)) -> AppointmentOut:
    appt = svc.get_by_code(db, code)
    if not appt:
        raise HTTPException(status_code=404, detail="Appuntamento non trovato.")
    return AppointmentOut.model_validate(appt)


@router.get("/slots/available", response_model=SlotsOut)
def slots(
    office: str = Query(...),
    target_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
) -> SlotsOut:
    try:
        slots = svc.available_slots(db, office, target_date)
    except svc.BookingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SlotsOut(
        office=office,
        date=target_date.isoformat(),
        available_slots=[s.isoformat() for s in slots],
    )
