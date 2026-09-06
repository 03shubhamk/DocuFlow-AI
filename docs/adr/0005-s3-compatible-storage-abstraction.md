# ADR 0005: S3-Compatible Object Storage Abstraction with MinIO

**Status:** Accepted  
**Date:** 2026-09-06  
**Deciders:** Principal Software Architect, Backend Team  
**Consulted:** DevOps  
**Informed:** Stakeholders  

---

## 1. Context & Problem Statement

DocuFlow AI manages large, heterogeneous binary assets across document lifecycles:
- Original uploaded files (PDF, DOCX, XLSX, scanned TIFF images) up to 50MB.
- Intermediate Docling structured JSON representations (often several megabytes for multi-page documents).
- Exported normalized Markdown files.
- Extracted visual assets (cropped figures, diagrams, and chart images).
- Extracted tabular CSV files.

Storing these binary payloads directly in PostgreSQL (via `BYTEA` or `Large Objects`) causes severe table bloat, drastically increases database backup times, exhausts RAM connection buffers, and impedes read replication.

Conversely, storing files on a local filesystem prevents horizontal scaling across multiple container instances and introduces high failure risk on container termination.

---

## 2. Decision Drivers

- **Scalability & Durability**: Infinite capacity to store terabytes of unstructured documents and visual assets without impacting database performance.
- **Stateless Application Tier**: Application and worker containers must remain completely stateless and disposable.
- **Secure Direct Access**: Support for generating time-limited presigned URLs (15-minute TTL) for secure streaming downloads without proxying large files through the API server.
- **Local Dev Parity**: Ability to develop and test offline against an exact S3-compatible API without incurring cloud costs or requiring internet access.

---

## 3. Considered Options

1. **PostgreSQL BYTEA**: Simpler single-database backup, but rapidly bloats database storage, degrades query cache efficiency, and hampers scaling.
2. **Local Filesystem / Network File System (NFS)**: Simple for a single server, but introduces POSIX locking issues, breaks container immutability, and does not scale in cloud container orchestrators (ECS/Kubernetes).
3. **S3-Compatible Object Storage (MinIO locally / AWS S3 or Cloudflare R2 in production)**: Industry-standard object storage accessible via unified S3 API (`boto3`).

---

## 4. Decision Outcome

**Chosen Option:** Option 3 — **S3-Compatible Object Storage Abstraction**.

We abstract all object storage behind a domain-level `StorageGateway` port, implemented by `S3StorageService` using `boto3`:
- **Local Development**: MinIO container running within `docker-compose.yml` on port 9000, initialized with default buckets via a one-shot `minio-init` container.
- **Production**: Native Amazon S3, Google Cloud Storage, or Cloudflare R2, configured simply by swapping environment variables (`S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`).

### Storage Hierarchy
```text
docuflow-documents/
└── tenants/{tenant_id}/
    └── documents/{document_id}/
        └── v{version}/
            ├── raw/{safe_filename}
            ├── parsed/docling_document.json
            ├── exports/content.md
            └── assets/
                ├── images/{image_id}.png
                └── tables/{table_id}.csv
```

### Positive Consequences
- **Stateless Horizontally Scalable Workloads**: Any worker or API pod can read or write assets using standard S3 URIs.
- **Presigned URL Efficiency**: File downloads can bypass the FastAPI server entirely by streaming directly from S3/MinIO via expiring presigned URLs, dramatically saving API bandwidth and compute.
- **100% Development Parity**: The exact same `boto3` codebase is executed during local unit/integration tests and live cloud deployments.
- **Object Versioning & Lifecycle Rules**: Production S3 buckets leverage automated lifecycle rules to transition archived document versions to cold storage (S3 Glacier) and enforce soft-deletion retention windows.

### Negative Consequences
- **Operational Requirement**: Requires spinning up a MinIO service during local development.
- **Mitigation**: MinIO is integrated into `docker-compose.yml` with automated bucket creation scripts, ensuring seamless zero-configuration local onboarding.
