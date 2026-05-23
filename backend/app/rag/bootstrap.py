"""Pre-warm the RAG pipeline: load the embedding model and verify the
services file. Safe to run on every container start.

The actual in-memory index is built when the FastAPI app boots
(see `app.main.lifespan`), so running this standalone simply validates
that the model can be loaded and the data is parseable. It also warms
the HuggingFace cache so the first user-facing request is fast.
"""

import logging

from app.rag.store import get_store, load_services_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    services = load_services_file()
    if not services:
        log.warning("No services to index. Run scripts/scrape_codroipo.py first.")
        return
    log.info("Found %d services. Pre-warming the embedding model…", len(services))
    n = get_store().index_services(services)
    log.info("RAG ready: %d chunks indexed in memory.", n)


if __name__ == "__main__":
    main()
