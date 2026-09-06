# DocuFlow AI — Infrastructure & Deployment Architecture

**Author:** Principal Software Architect  
**Status:** Approved  
**Version:** 1.0.0  
**Last Updated:** 2026-09-06  

---

## 1. Overview & Operational Principles

DocuFlow AI is architected according to **Twelve-Factor Application** principles, running as containerized workloads across both local developer workstations and enterprise production environments.

### Operational Principles
1. **Identical Dev and Prod Topologies**: Local development uses Docker Compose with local services (PostgreSQL, Redis, MinIO, Qdrant); production uses the exact same application container images backed by managed cloud infrastructure (AWS RDS, S3, Qdrant Cloud, ElastiCache).
2. **Immutable Containers**: Application containers are stateless and immutable. Configuration is strictly injected via validated environment variables.
3. **Least Privilege Runtime**: Containers execute under a non-root system user (`appuser`, UID 10001) with read-only root filesystems where applicable.
4. **Resilient Self-Healing**: Health probes (`/health/live`, `/health/ready`) enable orchestrators (Docker Swarm / Kubernetes) to automatically restart crashed workers or route traffic away from degraded API replicas.

---

## 2. Local Development Environment (Docker Compose)

The entire platform runs locally with a single command:
```bash
docker compose up --build
```

### 2.1 Multi-Service Topology
```text
docker-compose.yml
├── postgres:16-alpine         (Port 5432)  - Relational database
├── redis:7.2-alpine           (Port 6379)  - Broker & rate limit cache
├── minio                      (Port 9000: API, 9001: Web Console) - S3 Object Store
├── minio-init                 (One-shot)   - Auto-creates default S3 buckets
├── qdrant/qdrant:latest       (Port 6333)  - Vector database
├── backend-api                (Port 8000)  - FastAPI server with hot-reload
├── celery-worker-parsing      (Internal)   - Docling conversion & OCR worker
├── celery-worker-indexing     (Internal)   - Chunking & Qdrant indexing worker
└── frontend                   (Port 3000)  - Next.js web application with hot-module reload
```

### 2.2 Volume Persistence
- `postgres_data`: Persists relational state across container restarts.
- `minio_data`: Persists uploaded binary documents and exported assets.
- `qdrant_data`: Persists vector points and HNSW index graphs.
- `redis_data`: Persists Celery task state and rate-limiting counters.

---

## 3. Production Deployment Architecture

```mermaid
graph TB
    subgraph Public Internet
        Users[Web & API Users]
    end

    subgraph Edge Tier
        DNS[Route 53 / Cloudflare DNS]
        WAF[Cloudflare WAF / AWS WAF<br/>DDoS Mitigation, SSL Termination]
        CDN[Edge CDN<br/>Next.js Static Assets & Cached Views]
    end

    subgraph Ingress & Load Balancing
        ALB[Application Load Balancer<br/>HTTPS Path Routing]
    end

    subgraph Compute Tier: Container Orchestrator (ECS / K8s)
        subgraph Web Services
            FrontendNodes["Frontend Cluster<br/>(Next.js SSR Replicas)"]
            APINodes["API Cluster<br/>(FastAPI Stateless Replicas)"]
        end

        subgraph Asynchronous Workers
            ParsingWorkers["Parsing Worker Pool<br/>(High CPU/RAM: Docling + OCR)"]
            IndexingWorkers["Indexing Worker Pool<br/>(Balanced: Chunker + Embedder)"]
        end
    end

    subgraph Managed Cloud Data Tier
        RDS[("Amazon RDS PostgreSQL 16<br/>(Multi-AZ, Read Replicas)")]
        RedisCluster[("Amazon ElastiCache Redis<br/>(Multi-AZ with Replication)")]
        S3Bucket[("Amazon S3 Standard<br/>(Versioning, Lifecycle Rules)")]
        QdrantCluster[("Qdrant Cloud / Cluster<br/>(Distributed Vector Shards)")]
    end

    Users --> DNS
    DNS --> WAF
    WAF --> CDN
    WAF --> ALB

    ALB -->|Route /*| FrontendNodes
    ALB -->|Route /api/*| APINodes

    APINodes --> RedisCluster
    APINodes --> RDS
    APINodes --> S3Bucket
    APINodes --> QdrantCluster

    ParsingWorkers --> RedisCluster
    ParsingWorkers --> S3Bucket
    ParsingWorkers --> RDS

    IndexingWorkers --> RedisCluster
    IndexingWorkers --> S3Bucket
    IndexingWorkers --> RDS
    IndexingWorkers --> QdrantCluster
```

### 3.1 Resource Allocation Guidelines

| Workload | Recommended CPU | Recommended Memory | Scaling Metric |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend Replicas** | 1 - 2 vCPU | 2 GB | Target 65% CPU utilization / HTTP request latency |
| **Celery Parsing Workers** | 2 - 4 vCPU | 4 - 8 GB | Length of `docuflow.parsing` Redis queue |
| **Celery Indexing Workers**| 1 - 2 vCPU | 2 - 4 GB | Length of `docuflow.indexing` Redis queue |
| **Next.js Frontend** | 1 vCPU | 1 GB | HTTP request rate |

---

## 4. Multi-Stage Production Dockerfiles

### 4.1 Backend Dockerfile (`backend/Dockerfile`)
```dockerfile
# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --upgrade pip && pip install poetry && poetry export -f requirements.txt --output requirements.txt --without-hashes
RUN pip wheel --wheel-dir=/build/wheels -r requirements.txt

# Stage 2: Minimal Runtime
FROM python:3.11-slim AS runner

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    tesseract-ocr \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Create unprivileged service user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

COPY --chown=appuser:appgroup . /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 5. CI/CD Pipeline Architecture (GitHub Actions)

### 5.1 Continuous Integration (`.github/workflows/ci.yml`)
Triggers on all pull requests targeting `main`:
1. **Lint & Formatting**:
   - Python: `ruff check .` and `ruff format --check .`
   - TypeScript: `eslint src/` and `prettier --check .`
2. **Type Verification**:
   - Python: `mypy --strict app/`
   - TypeScript: `tsc --noEmit`
3. **Automated Unit & Integration Tests**:
   - Runs `pytest --cov=app --cov-report=xml` against temporary Dockerized PostgreSQL and Redis.
   - Requires minimum 85% branch coverage.
4. **Vulnerability Audit**:
   - `bandit -r app/` for Python AST security violations.
   - `pip-audit` for third-party CVE vulnerabilities.

### 5.2 Container Build & Release (`.github/workflows/docker-build.yml`)
Triggers on release tag or merge to `main`:
1. Logs in to GitHub Container Registry (`ghcr.io`).
2. Builds multi-architecture container images (`linux/amd64`, `linux/arm64`) using Docker Buildx.
3. Tags image with short commit SHA and `latest`.
4. Pushes artifacts to `ghcr.io/docuflow-ai/backend` and `ghcr.io/docuflow-ai/frontend`.

---

## 6. Environment Variable Configuration Strategy

Configuration is validated at startup using Pydantic Settings (`app/config.py`). If any mandatory variable is missing or invalid, the container fails fast.

| Variable Name | Type | Default | Sensitive | Description |
| :--- | :---: | :---: | :---: | :--- |
| `ENVIRONMENT` | String | `development` | No | `development`, `staging`, `production` |
| `DATABASE_URL` | String | *Required* | **Yes** | PostgreSQL connection URI (`postgresql+asyncpg://...`) |
| `REDIS_URL` | String | `redis://localhost:6379/0` | No | Celery message broker URI |
| `JWT_SECRET_KEY` | String | *Required* | **Yes** | Secret used for HMAC-SHA256 token signing |
| `JWT_ALGORITHM` | String | `HS256` | No | Algorithm for JWT tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Int | `15` | No | Access token validity window |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Int | `7` | No | Refresh token retention window |
| `S3_ENDPOINT_URL` | String | `http://localhost:9000` | No | Custom S3 endpoint (for MinIO) or None (for AWS S3) |
| `S3_ACCESS_KEY_ID` | String | *Required* | **Yes** | S3 / MinIO access key |
| `S3_SECRET_ACCESS_KEY` | String | *Required* | **Yes** | S3 / MinIO secret key |
| `S3_BUCKET_DOCUMENTS` | String | `docuflow-documents`| No | Primary storage bucket |
| `QDRANT_HOST` | String | `localhost` | No | Qdrant host address |
| `QDRANT_PORT` | Int | `6333` | No | Qdrant gRPC / HTTP port |
| `QDRANT_API_KEY` | String | None | **Yes** | Qdrant Cloud cluster API key |
| `MAX_UPLOAD_SIZE_BYTES` | Int | `52428800` (50MB) | No | Maximum permitted file upload size |
| `LOG_LEVEL` | String | `INFO` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## 7. Backup, Disaster Recovery & High Availability

### 7.1 PostgreSQL Recovery
- **Continuous Archiving**: Continuous WAL (Write-Ahead Logging) archiving enables Point-in-Time Recovery (PITR) up to the minute of any disaster.
- **Automated Snapshots**: Daily automated full database dumps (`pg_dump`) executed off-peak and copied to an immutable, versioned S3 bucket with 90-day retention.

### 7.2 S3 Storage Durability
- **Object Versioning**: Enabled across all document buckets to prevent catastrophic accidental deletion.
- **Cross-Region Replication**: In production, the raw document bucket is asynchronously mirrored to a secondary cloud region.

### 7.3 Qdrant Snapshot Replication
- Automated daily snapshot jobs trigger Qdrant's Snapshot API (`POST /collections/docuflow_chunks/snapshots`). The generated snapshots are automatically uploaded to S3.
- **RPO & RTO Targets**:
  - **Recovery Point Objective (RPO)**: < 15 minutes for metadata; 0 minutes for uploaded documents.
  - **Recovery Time Objective (RTO)**: < 60 minutes for complete cold-standby restoration.
