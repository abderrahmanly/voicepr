from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CallLogOut
from app.db.models import CallLog
from app.db.session import get_db

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("", response_model=list[CallLogOut])
def list_calls(db: Session = Depends(get_db)) -> list[CallLogOut]:
    rows = db.scalars(select(CallLog).order_by(CallLog.created_at.desc()).limit(100))
    return [CallLogOut.model_validate(r) for r in rows]
