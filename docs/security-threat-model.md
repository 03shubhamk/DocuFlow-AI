# DocuFlow AI — Production Security & Threat Model

This document outlines the security architecture, threat model, and defense-in-depth mitigations for the **DocuFlow AI** Document Intelligence and Semantic Search platform.

---

## 1. System Assets & Sensitivity Classification

| Asset | Description | Sensitivity | Storage Location |
|---|---|---|---|
| **User Credentials & Secrets** | Argon2/bcrypt password hashes, JWT HMAC keys | **Critical** | PostgreSQL (`users`), Environment |
| **Original Document Blobs** | Customer financial reports, proprietary PDFs, Office docs | **High** | MinIO / S3 Encrypted Storage |
| **Normalized Markdown & ASTs** | Parsed document layouts, tables, picture metadata | **High** | Object Storage (`artifacts/`) |
| **Document Chunk Embeddings** | Dense & sparse vector embeddings with text payloads | **High** | Qdrant Vector Database |
| **Multi-Tenant Metadata** | Tenant IDs, user profiles, processing job logs | **Medium** | PostgreSQL DB |
| **System Telemetry & Auditing** | Ingestion audit trails, request correlation logs | **Medium** | PostgreSQL (`audit_logs`) & Stdout |

---

## 2. STRIDE Threat Analysis & Defense Matrix

### 2.1 Spoofing (Identity & Token Attacks)
* **Threat**: Malicious actors forging JWT tokens or replaying stolen tokens.
* **Attack Vectors**:
  - Weak signature keys or `none` algorithm attacks.
  - Refresh token theft or reuse after token expiration.
* **Mitigations**:
  - `HS256` signed JWTs enforced with minimum 32-character high-entropy secret key.
  - Cryptographic refresh token hashing (SHA-256) and one-time rotation on every refresh.
  - Full refresh token family revocation on reuse detection.
  - Explicit token expiration (`access_token_expire_minutes=15`).

### 2.2 Tampering (Data Integrity Attacks)
* **Threat**: Modifying document chunks, altering embeddings, or bypassing file upload sanitization.
* **Attack Vectors**:
  - File extension spoofing (e.g. uploading a Linux ELF or Windows EXE disguised as `.pdf`).
  - Path traversal injection (`../../etc/passwd` in filename or zip archive members).
  - Malicious macro injection or embedded exploit payloads.
* **Mitigations**:
  - Magic byte and binary header verification against strict canonical signatures.
  - Executable signature rejection (`MZ`, `ELF`, Mach-O, shellcode).
  - Filename sanitization stripping directory traversal symbols (`..`, `/`, `\`, `%00`).
  - Asynchronous malware scanning abstraction (`MockMalwareScanner` / `ClamAVScanner`).
  - SHA-256 streaming checksum verification on all uploads.

### 2.3 Repudiation (Audit & Traceability)
* **Threat**: Actions performed without accountability or traceable provenance.
* **Mitigations**:
  - Structured audit trail table (`audit_logs`) recording user, tenant, action, and target entity.
  - End-to-end `X-Correlation-ID` header propagated across all API requests and logs.

### 2.4 Information Disclosure (Data Leakage & IDOR)
* **Threat**: User A accessing User B's documents or Tenant X reading Tenant Y's vector chunks.
* **Attack Vectors**:
  - Insecure Direct Object References (IDOR) via predictable UUID guessing.
  - Sensitive passwords or JWT tokens printed in application logs.
  - Vector similarity queries returning results across unauthorized tenant boundaries.
* **Mitigations**:
  - Multi-tenant query scoping: Every database query enforces `tenant_id` equality.
  - User ownership enforcement: Non-admin users are restricted to `user_id == current_user.id`.
  - Qdrant payload filters: Vector store queries enforce `tenant_id` and `user_id` payload matching.
  - Structlog redaction processor automatically stripping `password`, `token`, and `Bearer ...` strings.

### 2.5 Denial of Service (DoS & Resource Exhaustion)
* **Threat**: Attackers exhausting server memory or CPU through oversized payloads or decompression bombs.
* **Attack Vectors**:
  - Zip bombs (e.g. 10KB `.docx` expanding into 50GB uncompressed XML).
  - High-frequency API request flooding.
  - Multi-gigabyte file upload stream buffer exhaustion.
* **Mitigations**:
  - Streaming file size enforcement terminating uploads at `max_upload_size_bytes` (50MB).
  - OOXML Archive Bomb inspection: Max expansion ratio 100x, max uncompressed size 200MB, max 2000 member files.
  - Token bucket sliding-window rate limiting (`RateLimitingMiddleware`) returning `429 Too Many Requests`.
  - Maximum body size middleware rejecting oversized payloads before buffering in memory.

### 2.6 Elevation of Privilege (RBAC Violations)
* **Threat**: Viewer or Editor roles accessing administrative functions or triggering unauthorized cluster reindexing.
* **Mitigations**:
  - Role-based access control (`UserRole.ADMIN`, `UserRole.EDITOR`, `UserRole.VIEWER`) verified on protected endpoints.
  - Admin-only routes enforcing role checks before executing actions.

---

## 3. Zero-Trust Document Isolation Architecture

```
Client Request
      ↓
Authentication & RBAC Middleware (Extracts user_id, tenant_id, role)
      ↓
Repository & Service Layer (Zero IDOR Validation)
      ├── Database: WHERE tenant_id = :tenant_id AND (user_id = :user_id OR :is_admin)
      ├── Object Storage: tenants/{tenant_id}/documents/{document_id}/...
      └── Vector Store: Qdrant Match(tenant_id) & Match(user_id)
```

---

## 4. Frontend Security Safeguards

- **XSS Prevention**: React JSX automatic text escaping and sanitized Markdown rendering.
- **Safe Content Handling**: Document artifact downloads use forced `Content-Disposition: attachment` headers.
- **Session Protection**: Auth tokens cleared from browser storage on logout and on `401 Unauthorized` responses.
- **OWASP Security Headers**: Injected on all HTTP responses:
  - `Content-Security-Policy`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
