import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import appointments, calls, rag, vapi
from app.core.config import settings
from app.db import init_db
from app.rag.store import get_store, load_services_file

log = logging.getLogger("voicepr")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 1. ensure tables exist
    init_db.main()
    # 2. build in-memory RAG index from services.json
    services = load_services_file()
    if services:
        n = get_store().index_services(services)
        log.info("RAG indexed %d chunks from %d services", n, len(services))
    else:
        log.warning("RAG: no services file found — search will return empty hits")
    yield


app = FastAPI(
    title="Voicepr backend",
    description="Backend for the Codroipo voicebot prototype: RAG, appointments, Vapi tools.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appointments.router)
app.include_router(rag.router)
app.include_router(calls.router)
app.include_router(vapi.router)

# Static audio served to Vapi as backgroundSound URL
_audio_dir = Path(__file__).resolve().parent.parent / "data" / "audio"
if _audio_dir.exists():
    app.mount("/audio", StaticFiles(directory=str(_audio_dir)), name="audio")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "municipality": settings.municipality_name,
        "rag_chunks": get_store().count(),
    }
