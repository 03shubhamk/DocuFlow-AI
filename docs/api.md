# DocuFlow AI — REST API Architecture & Specification

**Author:** Principal Software Architect  
**Status:** Approved  
**Version:** 1.0.0  
**Last Updated:** 2026-09-06  

---

## 1. Design Philosophy & API Conventions

DocuFlow AI provides a clean, predictable, resource-oriented RESTful HTTP API built using **FastAPI** and validated with **Pydantic v2**.

### Core Standards
1. **URI Versioning**: Base path is strictly prefixed with `/api/v1`. Minor non-breaking updates occur within v1; breaking changes increment to `/api/v2`.
2. **HTTP Verb Semantics**:
   - `GET`: Safe, idempotent retrieval of resources.
   - `POST`: Create a resource or execute an asynchronous operation (e.g. search, retry).
   - `PUT / PATCH`: Full or partial resource updates.
   - `DELETE`: Remove or soft-delete a resource.
3. **Strict Content Negotiation**: `Content-Type: application/json` for standard requests and responses; `multipart/form-data` for file uploads.
4. **RFC 7807 Problem Details**: All error responses return standard Problem Details payloads with unique `correlation_id` tracking.
5. **Idempotency Keys**: Mutating operations (e.g., upload, retry) accept an `Idempotency-Key` header (UUIDv4) to guarantee safe re-execution without duplicate side effects.
6. **Rate Limiting**: Monitored via Redis token-bucket middleware with standard headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`).

---

## 2. Authentication & Authorization Flow

```mermaid
sequenceDiagram
    autonumber
    actor Client as Web Dashboard / API Client
    participant AuthAPI as /api/v1/auth
    participant Redis as Redis Blocklist
    participant ProtectedAPI as /api/v1/documents

    Client->>AuthAPI: POST /login {email, password}
    Note over AuthAPI: 1. Verify Argon2 hash<br/>2. Generate JWT Access Token (15m)<br/>3. Generate Refresh Token (7d)
    AuthAPI-->>Client: 200 OK {access_token, token_type: "bearer", expires_in: 900}<br/>Set-Cookie: refresh_token=... (HttpOnly; Secure; SameSite=Strict)

    Client->>ProtectedAPI: GET /api/v1/documents<br/>Authorization: Bearer <access_token>
    Note over ProtectedAPI: Validate JWT signature & tenant_id
    ProtectedAPI-->>Client: 200 OK {items: [...], total: 42}

    Note over Client: Access token expires (401 Unauthorized)
    Client->>AuthAPI: POST /refresh (Cookie: refresh_token)
    AuthAPI->>Redis: Check if refresh token revoked
    Note over AuthAPI: Generate new Access Token
    AuthAPI-->>Client: 200 OK {access_token, expires_in: 900}

    Client->>AuthAPI: POST /logout
    AuthAPI->>Redis: Add refresh token to revocation blocklist (TTL 7d)
    AuthAPI-->>Client: 204 No Content
```

---

## 3. Standardized Error Handling (RFC 7807)

Every non-2xx response adheres to the RFC 7807 Problem Details standard:

```json
{
  "type": "https://docuflow.ai/errors/unsupported-file-format",
  "title": "Unsupported File Format",
  "status": 415,
  "detail": "File 'financial_report.xyz' has unsupported MIME type 'application/octet-stream'. Accepted types: PDF, DOCX, PPTX, XLSX, HTML, Markdown, TXT, PNG, JPEG, TIFF.",
  "instance": "/api/v1/documents/upload",
  "correlation_id": "req-98f21bc0-1122-4455-6677",
  "invalid_params": [
    {
      "name": "file",
      "reason": "File signature does not match any allowed format."
    }
  ]
}
```

### Common HTTP Status Codes
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully created.
- `202 Accepted`: Asynchronous task queued for processing (e.g. document ingestion).
- `204 No Content`: Resource deleted or action executed with no response body.
- `400 Bad Request`: Malformed JSON or invalid parameters.
- `401 Unauthorized`: Missing or invalid Bearer JWT.
- `403 Forbidden`: Authenticated user lacks permission or crosses tenant boundary.
- `404 Not Found`: Resource does not exist.
- `409 Conflict`: Concurrency conflict or duplicate file checksum.
- `415 Unsupported Media Type`: Invalid or disallowed file MIME type.
- `422 Unprocessable Entity`: Pydantic schema validation failure.
- `429 Too Many Requests`: Rate limit threshold exceeded.
- `500 Internal Server Error`: Unhandled server exception with correlation ID logged.

---

## 4. Detailed Endpoint Specifications

### 4.1 Authentication (`/api/v1/auth`)

#### `POST /api/v1/auth/register`
Creates a new user account, optionally assigning them to a new organizational tenant workspace.
- **Request Body** (`application/json`):
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!",
    "full_name": "Jane Doe",
    "tenant_name": "Acme Corp",
    "role": "USER"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "id": "7ca64e81-b518-4b72-97fc-112233445566",
    "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@example.com",
    "full_name": "Jane Doe",
    "role": "USER",
    "is_active": true,
    "created_at": "2026-09-08T00:00:00Z"
  }
  ```

#### `POST /api/v1/auth/login`
Authenticates a user with email and password, issuing an access JWT (15m) and rotating refresh token (7d).
- **Request Body** (`application/json`):
  ```json
  {
    "email": "user@example.com",
    "password": "StrongPassword123!"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "refresh_token": "u_k9a2j3N-8x...",
    "token_type": "bearer",
    "expires_in": 900
  }
  ```

#### `POST /api/v1/auth/refresh`
Rotates an active refresh token. Revokes the old refresh token in the database and returns a brand-new token pair.
- **Request Body** (`application/json`):
  ```json
  {
    "refresh_token": "u_k9a2j3N-8x..."
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "refresh_token": "v_m8b3k4O-9y...",
    "token_type": "bearer",
    "expires_in": 900
  }
  ```

#### `POST /api/v1/auth/logout`
Revokes the refresh token session in the database.
- **Headers**: `Authorization: Bearer <access_token>`
- **Request Body** (optional): `{ "refresh_token": "..." }`
- **Response**: `200 OK`
  ```json
  {
    "detail": "Successfully logged out."
  }
  ```

#### `GET /api/v1/auth/me`
Retrieves the profile and permissions of the currently authenticated user.
- **Headers**: `Authorization: Bearer <access_token>`
- **Response**: `200 OK`
  ```json
  {
    "id": "7ca64e81-b518-4b72-97fc-112233445566",
    "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@example.com",
    "full_name": "Jane Doe",
    "role": "USER",
    "is_active": true,
    "created_at": "2026-09-08T00:00:00Z"
  }
  ```

---

### 4.2 Documents (`/api/v1/documents`)

#### `POST /api/v1/documents`
Securely uploads a document for processing with zero-trust validation (magic bytes, extension whitelist, streaming SHA-256 calculation, and duplicate detection).
- **Headers**:
  - `Authorization: Bearer <token>`
- **Request**: `multipart/form-data`
  - `file`: Binary file stream (max 50MB). Supported formats: PDF, DOCX, PPTX, XLSX, HTML, MD, TXT, PNG, JPG, JPEG, TIFF.
  - `title`: String (Optional, defaults to sanitized filename)
- **Response**: `201 Created`
  ```json
  {
    "document": {
      "id": "8aa64e81-b518-4b72-97fc-112233445566",
      "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "owner_id": "7ca64e81-b518-4b72-97fc-112233445566",
      "title": "Quarterly_Financials_Q3.pdf",
      "original_filename": "Quarterly_Financials_Q3.pdf",
      "file_type": ".pdf",
      "file_size_bytes": 4194304,
      "storage_path": "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
      "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "is_deleted": false,
      "created_at": "2026-09-08T00:00:00Z",
      "updated_at": "2026-09-08T00:00:00Z"
    },
    "job": {
      "id": "c7113112-9988-7766-5544-33221100aabb",
      "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
      "version_id": "18f92113-1122-3344-5566-778899aabbcc",
      "status": "UPLOADED",
      "stage": "INGESTION",
      "progress_percent": 0,
      "created_at": "2026-09-08T00:00:00Z",
      "updated_at": "2026-09-08T00:00:00Z"
    },
    "message": "Document uploaded successfully and queued for processing."
  }
  ```

#### `GET /api/v1/documents`
Lists documents accessible to the authenticated user with pagination, keyword search, filtering, and sorting.
- **Headers**: `Authorization: Bearer <token>`
- **Query Parameters**:
  - `page`: Integer (default `1`, min `1`)
  - `page_size`: Integer (default `20`, min `1`, max `100`)
  - `file_type`: Filter by extension (e.g. `.pdf`, `.docx`)
  - `search`: Search query matching title or original filename
  - `sort_by`: `created_at` | `title` | `file_size_bytes` (default: `created_at`)
  - `order`: `asc` | `desc` (default: `desc`)
- **Response**: `200 OK`
  ```json
  {
    "items": [
      {
        "id": "8aa64e81-b518-4b72-97fc-112233445566",
        "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "owner_id": "7ca64e81-b518-4b72-97fc-112233445566",
        "title": "Quarterly_Financials_Q3.pdf",
        "original_filename": "Quarterly_Financials_Q3.pdf",
        "file_type": ".pdf",
        "file_size_bytes": 4194304,
        "storage_path": "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
        "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "is_deleted": false,
        "created_at": "2026-09-08T00:00:00Z",
        "updated_at": "2026-09-08T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 1,
      "total_pages": 1,
      "has_next": false,
      "has_previous": false
    }
  }
  ```

#### `GET /api/v1/documents/{document_id}`
Retrieves complete details for a document, including version snapshots, derived assets, and latest processing job status.
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `200 OK`
  ```json
  {
    "id": "8aa64e81-b518-4b72-97fc-112233445566",
    "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "owner_id": "7ca64e81-b518-4b72-97fc-112233445566",
    "title": "Quarterly_Financials_Q3.pdf",
    "original_filename": "Quarterly_Financials_Q3.pdf",
    "file_type": ".pdf",
    "file_size_bytes": 4194304,
    "storage_path": "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
    "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "is_deleted": false,
    "created_at": "2026-09-08T00:00:00Z",
    "updated_at": "2026-09-08T00:00:00Z",
    "versions": [
      {
        "id": "18f92113-1122-3344-5566-778899aabbcc",
        "version_number": 1,
        "storage_path": "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
        "file_size_bytes": 4194304,
        "checksum_sha256": "e3b0c442...",
        "created_at": "2026-09-08T00:00:00Z"
      }
    ],
    "assets": [
      {
        "id": "29f92113-2233-4455-6677-8899aabbccdd",
        "version_id": "18f92113-1122-3344-5566-778899aabbcc",
        "asset_type": "ORIGINAL",
        "storage_path": "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 4194304,
        "created_at": "2026-09-08T00:00:00Z"
      }
    ],
    "latest_job": {
      "id": "c7113112-9988-7766-5544-33221100aabb",
      "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
      "version_id": "18f92113-1122-3344-5566-778899aabbcc",
      "status": "UPLOADED",
      "stage": "INGESTION",
      "progress_percent": 0,
      "created_at": "2026-09-08T00:00:00Z",
      "updated_at": "2026-09-08T00:00:00Z"
    }
  }
  ```

#### `DELETE /api/v1/documents/{document_id}`
Soft-deletes a document and records the deletion in the immutable audit log. Soft-deleted documents are excluded from queries and listings.
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `200 OK`
  ```json
  {
    "message": "Document deleted successfully.",
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566"
  }
  ```

#### `POST /api/v1/documents/{document_id}/process`
Queues a document version for asynchronous Document Intelligence processing (Docling layout AST, tables, OCR, figures, and markdown).
- **Headers**: `Authorization: Bearer <token>`
- **Request Body** (optional):
  ```json
  {
    "do_ocr": true,
    "ocr_provider": "easyocr",
    "extract_figures": true,
    "do_table_structure": true
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "id": "c7113112-9988-7766-5544-33221100aabb",
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
    "version_id": "18f92113-1122-3344-5566-778899aabbcc",
    "status": "QUEUED",
    "stage": "INGESTION",
    "progress_percent": 0,
    "created_at": "2026-09-08T00:00:00Z",
    "updated_at": "2026-09-08T00:00:00Z"
  }
  ```

#### `GET /api/v1/documents/{document_id}/processing-status`
Returns real-time processing stage, progress percentage, error diagnostics, and generated artifact storage keys.
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `200 OK`
  ```json
  {
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
    "version_id": "18f92113-1122-3344-5566-778899aabbcc",
    "job_id": "c7113112-9988-7766-5544-33221100aabb",
    "status": "COMPLETED",
    "stage": "INDEXING_READY",
    "progress_percent": 100,
    "retry_count": 0,
    "max_retries": 3,
    "started_at": "2026-09-08T00:00:01Z",
    "completed_at": "2026-09-08T00:00:03Z",
    "duration_ms": 1845.2,
    "errors": [],
    "artifacts_created": [
      "tenants/3fa85f64.../documents/8aa64e81.../v1/8aa64e81_e3b0c442.pdf",
      "tenants/3fa85f64.../documents/8aa64e81.../v1/artifacts/document.json",
      "tenants/3fa85f64.../documents/8aa64e81.../v1/artifacts/document.md",
      "tenants/3fa85f64.../documents/8aa64e81.../v1/figures/picture_001.png"
    ]
  }
  ```

#### `GET /api/v1/documents/{document_id}/assets/{asset_type}`


Generates a secure presigned download URL for an asset.
- **Path Parameters**:
  - `asset_type`: `ORIGINAL` | `PARSED_JSON` | `EXPORT_MARKDOWN` | `EXTRACTED_IMAGE` | `TABLE_CSV`
- **Response**: `200 OK`
  ```json
  {
    "asset_type": "EXPORT_MARKDOWN",
    "download_url": "https://s3.docuflow.ai/docuflow-documents/...presigned_signature...",
    "expires_in_seconds": 900,
    "mime_type": "text/markdown"
  }
  ```

#### `GET /api/v1/documents/{document_id}/chunks`
Returns paginated chunks extracted from the document with heading breadcrumbs and bounding boxes.
- **Response**: `200 OK`
  ```json
  {
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
    "chunks": [
      {
        "id": "a901e012-3344-5566-7788-99aabbccddee",
        "chunk_index": 0,
        "content": "# Executive Summary\nIn Q3 2026, operating revenue expanded...",
        "token_count": 84,
        "heading_hierarchy": ["1. Executive Summary"],
        "page_numbers": [1],
        "chunk_metadata": {
          "item_type": "section_header",
          "bounding_box": {"l": 54.0, "t": 72.0, "r": 540.0, "b": 110.0}
      }
    ],
    "total": 48
  }
  ```

#### `POST /api/v1/documents/{document_id}/reindex`
Regenerates dense vector representations for all chunks of the latest document version and idempotently upserts them into the Qdrant vector database.
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `200 OK`
  ```json
  {
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
    "version_id": "18f92113-1122-3344-5566-778899aabbcc",
    "status": "INDEXED",
    "chunks_indexed": 48,
    "model_name": "BAAI/bge-small-en-v1.5",
    "dimension": 384,
    "message": "Document re-indexed successfully."
  }
  ```

---

### 4.3 Processing Jobs (`/api/v1/jobs`)

#### `GET /api/v1/jobs/{job_id}`
Returns real-time job stage, progress percentage, and diagnostic errors.
- **Response**: `200 OK`
  ```json
  {
    "job_id": "c7113112-9988-7766-5544-33221100aabb",
    "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
    "status": "PROCESSING",
    "stage": "DOCLING_PARSING",
    "progress_percent": 45,
    "retry_count": 0,
    "max_retries": 3,
    "started_at": "2026-09-06T12:05:02Z",
    "completed_at": null,
    "errors": []
  }
  ```

#### `POST /api/v1/jobs/{job_id}/retry`
Triggers an idempotent retry for a failed or stalled processing job.
- **Response**: `202 Accepted` `{ "job_id": "...", "status": "QUEUED" }`

#### `POST /api/v1/jobs/{job_id}/cancel`
Aborts an active job and revokes the corresponding Celery task.
- **Response**: `200 OK` `{ "job_id": "...", "status": "CANCELLED" }`

---

### 4.4 Semantic & Hybrid Search (`/api/v1/search`)

#### `POST /api/v1/search`
Performs vector semantic or hybrid search over document chunks.
- **Request Body**:
  ```json
  {
    "query": "What was the operating revenue in Q3?",
    "limit": 5,
    "score_threshold": 0.65,
    "filters": {
      "document_ids": ["8aa64e81-b518-4b72-97fc-112233445566"],
      "file_types": ["application/pdf"],
      "page_numbers": [1, 2, 3]
    },
    "hybrid": true
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "query": "What was the operating revenue in Q3?",
    "total_results": 1,
    "results": [
      {
        "chunk_id": "a901e012-3344-5566-7788-99aabbccddee",
        "document_id": "8aa64e81-b518-4b72-97fc-112233445566",
        "document_title": "Quarterly_Financials_Q3.pdf",
        "score": 0.892,
        "content": "Operating revenue for Q3 2026 reached $14.2M, representing a 15% increase year-over-year...",
        "heading_hierarchy": ["1. Executive Summary", "1.2 Revenue Breakdown"],
        "page_numbers": [1],
        "chunk_index": 4
      }
    ]
  }
  ```

---

### 4.5 Health & Metrics (`/health`)

- `GET /health/live`: `200 OK` `{ "status": "alive" }`
- `GET /health/ready`: Deep health check.
  - Returns `200 OK` if all dependencies (PostgreSQL, Redis, MinIO, Qdrant) are reachable.
  - Returns `503 Service Unavailable` with individual component statuses if degraded.
- `GET /health/metrics`: Exposes Prometheus text-format application metrics.
