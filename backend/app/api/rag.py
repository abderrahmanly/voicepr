from fastapi import APIRouter

from app.api.schemas import RagHit, RagSearchIn, RagSearchOut
from app.rag.store import get_store

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=RagSearchOut)
def search(body: RagSearchIn) -> RagSearchOut:
    store = get_store()
    hits = store.search(body.query, top_k=body.top_k)
    context = "\n\n---\n\n".join(
        f"[{h['title']}] {h['text']}" + (f"\nFonte: {h['url']}" if h.get("url") else "")
        for h in hits
    )
    return RagSearchOut(
        query=body.query,
        hits=[RagHit(**h) for h in hits],
        answer_context=context,
    )
