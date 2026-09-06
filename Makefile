# ==============================================================================
# DocuFlow AI — Developer Automation Makefile
# ==============================================================================

.PHONY: help dev up down restart logs build test test-backend test-frontend lint format clean migrate

help:
	@echo "DocuFlow AI Developer Commands:"
	@echo "  make up            - Start all services with Docker Compose"
	@echo "  make down          - Stop all Docker Compose containers"
	@echo "  make restart       - Restart all containers"
	@echo "  make logs          - View streaming container logs"
	@echo "  make build         - Build container images"
	@echo "  make test          - Run both backend and frontend tests"
	@echo "  make test-backend  - Run backend unit and integration tests"
	@echo "  make test-frontend - Run frontend tests"
	@echo "  make lint          - Run linters (ruff, eslint)"
	@echo "  make format        - Format code (ruff format, prettier)"
	@echo "  make migrate       - Run Alembic database migrations"
	@echo "  make clean         - Clean temporary cache and build files"

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

build:
	docker compose build

test: test-backend test-frontend

test-backend:
	cd backend && pytest -v --cov=app

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

format:
	cd backend && ruff format .
	cd frontend && npm run format

migrate:
	cd backend && alembic upgrade head

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".next" -exec rm -rf {} +
