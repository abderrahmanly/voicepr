"""In-memory RAG store backed by sentence-transformers + numpy cosine.

Why not Chroma/FAISS? The dataset for this prototype is ~30 chunks; an
in-memory float32 matrix is faster, has zero install friction across
Python versions, and keeps the dependency surface minimal. For a real
deployment you'd swap this for a persistent vector DB without changing
the public interface (`index_services`, `search`).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np

from app.core.config import settings

log = logging.getLogger(__name__)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


@dataclass
class Chunk:
    id: str
    text: str
    title: str
    url: str | None
    office: str | None


class RagStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._matrix: np.ndarray | None = None  # (N, D) L2-normalized
        self._encoder = None
        self._encoder_lock = Lock()

    # ---- embedding ------------------------------------------------------

    def _get_encoder(self):
        if self._encoder is None:
            with self._encoder_lock:
                if self._encoder is None:
                    from sentence_transformers import SentenceTransformer

                    log.info("Loading embedding model: %s", settings.embedding_model)
                    self._encoder = SentenceTransformer(settings.embedding_model)
        return self._encoder

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self._get_encoder()
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    # ---- chunking -------------------------------------------------------

    @staticmethod
    def _chunk(text: str) -> list[str]:
        text = " ".join(text.split())
        if len(text) <= CHUNK_SIZE:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_SIZE)
            if end < len(text):
                pivot = text.rfind(". ", start, end)
                if pivot > start + CHUNK_SIZE // 2:
                    end = pivot + 1
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
        return [c for c in chunks if c]

    # ---- index / search -------------------------------------------------

    def reset(self) -> None:
        self._chunks = []
        self._matrix = None

    def index_services(self, services: list[dict]) -> int:
        chunks: list[Chunk] = []
        for svc in services:
            sid = svc["id"]
            title = svc.get("title", "")
            url = svc.get("url") or None
            office = svc.get("office") or None
            body = (svc.get("content") or "").strip()
            if not body:
                continue
            full = f"{title}\n\n{body}"
            for i, txt in enumerate(self._chunk(full)):
                chunks.append(Chunk(id=f"{sid}::{i}", text=txt, title=title, url=url, office=office))

        if not chunks:
            return 0

        vectors = self._embed([c.text for c in chunks])
        self._chunks = chunks
        self._matrix = vectors  # already L2-normalized
        # Persist a tiny manifest so other processes can see we ran
        manifest = Path(settings.chroma_dir) / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps({"chunks": len(chunks), "model": settings.embedding_model}),
            encoding="utf-8",
        )
        return len(chunks)

    def count(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        if self._matrix is None or self.count() == 0:
            return []
        qvec = self._embed([query])[0]
        # cosine similarity == dot product on L2-normalized vectors
        sims = self._matrix @ qvec
        idx = np.argsort(-sims)[:top_k]
        hits: list[dict] = []
        for i in idx:
            c = self._chunks[int(i)]
            hits.append({
                "text": c.text,
                "title": c.title,
                "url": c.url,
                "office": c.office,
                "score": round(float(sims[int(i)]), 4),
            })
        return hits


_store: RagStore | None = None
_store_lock = Lock()


def get_store() -> RagStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = RagStore()
    return _store


def load_services_file(path: str | None = None) -> list[dict]:
    p = Path(path or settings.services_file)
    if not p.exists():
        log.warning("Services file missing: %s", p)
        return []
    return json.loads(p.read_text(encoding="utf-8"))
