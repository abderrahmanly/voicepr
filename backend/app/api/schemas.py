from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    citizen_name: str = Field(..., min_length=2, max_length=120)
    fiscal_code: str | None = Field(None, max_length=32)
    phone: str | None = Field(None, max_length=32)
    office: str = Field(..., min_length=2, max_length=80)
    reason: str | None = Field(None, max_length=500)
    scheduled_at: datetime


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    citizen_name: str
    fiscal_code: str | None
    phone: str | None
    office: str
    reason: str | None
    scheduled_at: datetime
    status: str
    created_at: datetime


class SlotsQuery(BaseModel):
    office: str
    date: str  # ISO date YYYY-MM-DD


class SlotsOut(BaseModel):
    office: str
    date: str
    available_slots: list[str]  # ISO datetime strings


class RagSearchIn(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(4, ge=1, le=10)


class RagHit(BaseModel):
    text: str
    title: str
    url: str | None = None
    score: float


class RagSearchOut(BaseModel):
    query: str
    hits: list[RagHit]
    answer_context: str  # concatenated chunks ready to drop into a prompt


class CallLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    call_id: str
    started_at: datetime | None
    ended_at: datetime | None
    ended_reason: str | None
    summary: str | None
    transcript: str | None
    recording_url: str | None
    created_at: datetime
