# DocuFlow AI — Production Document Intelligence & Ingestion Platform

[![CI](https://github.com/03shubhamk/DocuFlow-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/03shubhamk/DocuFlow-AI)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16%2B-black.svg)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://postgresql.org)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-dc2626.svg)](https://qdrant.tech)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**DocuFlow AI** is an enterprise-ready Document Intelligence and AI Ingestion Platform built for high-throughput multimodal document parsing, semantic chunking, vector embedding, hybrid search, and RAG ingestion.

---

## Architecture Overview

DocuFlow AI is architected using **Clean Architecture / Hexagonal Architecture** principles, enforcing strict separation of concerns across Domain, Application, Infrastructure, and Interface layers.

```
                    ┌────────────────────────┐
                    │      Next.js 16        │
                    │   (Frontend UI / App)  │
                    └───────────┬────────────┘
                                │ HTTP / REST
                                ▼
                    ┌────────────────────────┐
                    │    FastAPI Gateway     │
                    │  (Async API / Auth)    │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  PostgreSQL   │       │ Redis/Celery  │       │  MinIO / S3   │
│  (Metadata,   │       │ (Async Worker │       │  (Artifacts & │
│  Audit, Jobs) │       │  Docling OCR) │       │  Raw Files)   │
└───────────────┘       └───────┬───────┘       └───────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │    Qdrant     │
                        │ (Vector Store │
                        │  Dense/Sparse)│
                        └───────────────┘
```

### Key Capabilities
- **Multimodal Document Parsing**: PDF, DOCX, PPTX, XLSX, HTML, Markdown, TXT, Images (PNG, JPEG, TIFF) via IBM Docling.
- **Structural Extraction**: Hierarchy, reading order, sections, headings, tables with caption metadata, bounding boxes.
- **Hierarchical & Semantic Chunking**: Chunking aware of document layout, parent sections, and token boundaries.
- **Hybrid Search**: Vector dense embeddings + BM25 sparse keyword search with reciprocal rank fusion (RRF).
- **Multi-Tenant & Security**: Tenant data isolation, JWT authentication, and RFC 7807 problem details.
- **High Observability**: Structlog structured JSON logging, distributed correlation IDs, Prometheus metrics, and deep health probes.

---

## Repository Structure

```
DocuFlow AI/
├── backend/
│   ├── alembic/                # Database migrations (PostgreSQL DDL)
│   ├── app/
│   │   ├── api/                # API Routers, Middleware, Dependencies
│   │   │   ├── v1/             # Versioned REST endpoints (health, docs, jobs, search)
│   │   ├── application/        # Application Use Cases & DTOs
│   │   ├── domain/             # Entities, Value Objects, Domain Exceptions, Interfaces
│   │   ├── infrastructure/     # Database (SQLAlchemy 2.0), Storage (S3), Vector (Qdrant), Tasks (Celery)
│   │   ├── config.py           # Pydantic Settings configuration
│   │   └── main.py             # FastAPI App Factory & Lifespan
│   ├── tests/                  # Pytest Unit & Integration test suite
│   ├── Dockerfile              # Multi-stage production container build
│   ├── pyproject.toml          # Poetry / Ruff / Mypy / Pytest configuration
│   └── requirements.txt        # Pinned runtime dependencies
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router (Dashboard, Layout, Error Boundary, Loading)
│   │   ├── lib/                # API Client abstraction & utilities
│   │   └── types/              # TypeScript API contracts
│   ├── Dockerfile              # Production Next.js standalone container
│   ├── package.json            # Node.js dependencies & scripts
│   └── vitest.config.ts        # Frontend test configuration
├── docs/                       # Architecture decisions (ADRs) & System specifications
├── scripts/                    # Developer setup scripts (PowerShell / Bash)
├── docker-compose.yml          # Full local stack (PostgreSQL, Redis, MinIO, Qdrant, Backend, Celery, Frontend)
├── docker-compose.prod.yml     # Hardened production stack
├── Makefile                    # Developer CLI commands
└── .env.example                # Canonical environment variable template
```

---

## Quick Start (Local Development)

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** and **npm**
- **Docker** and **Docker Compose**

### 1. Clone & Configure Environment
```bash
git clone https://github.com/03shubhamk/DocuFlow-AI.git
cd "DocuFlow AI"

# Copy environment variables
cp .env.example .env
```

### 2. Start Full Infrastructure Stack (Docker Compose)
```bash
# Starts PostgreSQL (5432), Redis (6379), MinIO (9000/9001), Qdrant (6333), Backend, Celery, and Frontend
docker compose up -d
```

Access the services:
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Interactive Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001) (User: `minioadmin` / Pass: `minioadmin`)
- **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## Developer Workflows

### Backend Development
```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests with coverage
pytest --cov=app --cov-report=term-missing

# Lint and Format
ruff check app tests --fix
ruff format app tests
mypy app

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Run unit tests
npm test

# Run linter
npm run lint

# Build production bundle
npm run build

# Start Next.js dev server
npm run dev
```

---

## Testing Matrix

| Component | Framework | Command | Target |
|---|---|---|---|
| **Backend Unit & Integration** | `pytest` + `pytest-asyncio` | `pytest -v` | 100% Core Domain & API tests |
| **Backend Type Safety** | `mypy` (strict mode) | `mypy app` | Zero type errors |
| **Backend Code Quality** | `ruff` | `ruff check app tests` | Zero lint errors |
| **Frontend Tests** | `vitest` | `npm test` | API client & component tests |
| **Frontend Type Safety** | `tsc` | `npm run build` | Next.js compilation & TS check |

---

## CI/CD Pipeline & Automated Releases

DocuFlow AI includes production GitHub Actions workflows for continuous integration and gated releases:

- **Pull Request CI** (`.github/workflows/ci.yml`): Parallel jobs for Ruff linting, formatting, Mypy static typing, Alembic migration validation, Pytest unit/integration test suite, Vitest frontend tests, Next.js production builds, security vulnerability audits (`pip-audit`, `npm audit`, Trivy), and multi-stage Docker build validation.
- **Production Build & Deploy** (`.github/workflows/build.yml`): Automated multi-architecture container build, OCI semantic version tagging (`sha-*`, `v*`, `latest`), GitHub Container Registry (`ghcr.io`) publishing, staging deployment, and approval-gated production releases.

For comprehensive details on setting up secrets, environment protection rules, and local simulation, see [CI/CD Documentation](docs/cicd.md).

---

## Roadmap

- [x] **Phase 1: Project Foundation** — Clean architecture, Docker compose, FastAPI async scaffold, Next.js UI, test harnesses.
- [x] **Phase 2: Ingestion & Parsing Engine** — IBM Docling integration, multi-format parsing, layout analysis, S3 asset extraction.
- [x] **Phase 3: Chunking & Vector Ingestion** — Hierarchical chunker, FastEmbed embeddings, Qdrant indexing, batch pipeline.
- [x] **Phase 4: Retrieval & Query Engine** — Hybrid search (dense + sparse), reciprocal rank fusion, reranker, citation engine.
- [x] **Phase 5: Document Normalization & Intelligent Chunking** — Unicode normalization, AST preservation, metadata extraction.
- [x] **Phase 6: Embedding Generation & Qdrant Indexing** — FastEmbed provider abstraction, idempotent vector store indexer.
- [x] **Phase 7: Production Document Search** — SearchService, dense/hybrid strategies, threshold filtering.
- [x] **Phase 8: Complete Production Frontend** — 14 Next.js pages, dark mode glassmorphism UI, real-time job polling.
- [x] **Phase 9: Production Security Hardening** — OWASP security headers, sliding window rate limiting, IDOR prevention, EICAR malware scanning.
- [x] **Phase 10: Production Observability** — Prometheus metrics registry, OpenTelemetry tracing, W3C traceparent propagation, structured logging.
- [x] **Phase 11: Comprehensive Testing** — 170+ unit, integration, Celery, and end-to-end test pyramid.
- [x] **Phase 12: Performance & Scalability** — Database indexes, streaming memory bounding, Celery exponential backoff, benchmark suites.
- [x] **Phase 13: Production CI/CD** — GitHub Actions PR quality gates, multi-stage Docker builds, security scanners, gated production deployments.

---

## License
Apache License 2.0. See [LICENSE](LICENSE) for details.
