.PHONY: help up down logs restart build clean reindex test-backend smoke

help:
	@echo "Voicepr — common commands"
	@echo ""
	@echo "  make up           Start db + backend + frontend (Docker Compose)"
	@echo "  make down         Stop everything"
	@echo "  make logs         Tail backend logs"
	@echo "  make restart      Restart backend"
	@echo "  make build        Rebuild images"
	@echo "  make reindex      Force-rebuild the RAG index from data/services.json"
	@echo "  make clean        Remove containers and volumes (DESTRUCTIVE)"
	@echo "  make smoke        Hit local endpoints to verify the stack"

up:
	docker compose up -d --build
	@echo "Backend: http://localhost:8000/docs   ·   Frontend: http://localhost:8080"

down:
	docker compose down

logs:
	docker compose logs -f backend

restart:
	docker compose restart backend

build:
	docker compose build

reindex:
	docker compose exec -e VOICEPR_FORCE_REINDEX=1 backend python -m app.rag.bootstrap

clean:
	docker compose down -v

smoke:
	@./scripts/smoke.sh
