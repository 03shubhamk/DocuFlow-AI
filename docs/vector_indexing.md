# Vector Embedding & Qdrant Indexing Architecture

## 1. Overview

Phase 6 implements a production-grade, configurable vector embedding and semantic search indexing pipeline for DocuFlow AI. It takes structured `DocumentChunk` records produced by Phase 5, generates dense vector representations using configurable embedding providers (FastEmbed ONNX runtime or Mock provider for testing), and idempotently indexes them into a Qdrant vector database collection with multi-tenant payload isolation and metadata indexing.

```
DocumentChunk Record (PostgreSQL)
              ↓
      EmbeddingService
  (Batch processing, token limits)
              ↓
     EmbeddingProvider
  (FastEmbed ONNX runtime | Sentence-Transformers | Mock)
              ↓
    Dense Vector Representation
              ↓
     QdrantVectorStore
  ├── Deterministic UUID (uuid5)
  ├── Payload Filters (tenant_id, document_id, user_id)
  └── Payload Indexes (Keyword, Integer)
              ↓
  Qdrant Collection ("docuflow_chunks")
  & EmbeddingRecordModel (PostgreSQL Audit)
```

---

## 2. Configuration & Model Selection

All embedding and vector database parameters are centralized and environment-driven in `app.config.Settings`:

| Setting | Default Value | Description |
|---|---|---|
| `EMBEDDING_PROVIDER` | `fastembed` | Embedding engine (`fastembed`, `sentence-transformers`, `openai`, `mock`). |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Model identifier loaded by provider. |
| `EMBEDDING_DIMENSION` | `384` | Dimension of output dense vector representations. |
| `EMBEDDING_BATCH_SIZE` | `32` | Maximum number of chunks embedded per inference batch. |
| `QDRANT_HOST` | `qdrant` | Hostname of Qdrant vector database. |
| `QDRANT_PORT` | `6333` | REST / gRPC port for Qdrant. |
| `QDRANT_COLLECTION` | `docuflow_chunks` | Primary Qdrant vector collection name. |
| `QDRANT_DISTANCE` | `Cosine` | Distance metric for vector search (`Cosine`, `Dot`, `Euclid`). |

---

## 3. Provider Abstraction (`EmbeddingProvider`)

The `EmbeddingProvider` abstract base class decouples the application from specific AI libraries or vendors:

```python
class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]: ...
```

### Implementations:
1. **`FastEmbedProvider`**: Uses Qdrant's `fastembed` library powered by the ONNX Runtime for high-performance CPU inference without PyTorch/CUDA overhead. Default model `BAAI/bge-small-en-v1.5` (384 dimensions).
2. **`MockEmbeddingProvider`**: Computes deterministic unit-normalized float vectors derived from text SHA-256 hashes. Used automatically during test execution (`ENVIRONMENT=testing`) for lightning-fast, zero-network, zero-download test suites.

---

## 4. Qdrant Payload Schema & Filtering

Every vector point indexed in Qdrant contains rich structured metadata:

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "version_id": "7b13df18-4444-486a-bc01-38e219714eb8",
  "chunk_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "tenant_id": "11111111-1111-1111-1111-111111111111",
  "user_id": "22222222-2222-2222-2222-222222222222",
  "page_number": 1,
  "page_numbers": [1],
  "section_path": "Introduction > Architecture Overview",
  "heading_hierarchy": ["Introduction", "Architecture Overview"],
  "chunk_index": 0,
  "filename": "annual_report.pdf",
  "mime_type": ".pdf",
  "text": "DocuFlow AI provides robust document intelligence...",
  "token_count": 128,
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

### Automatic Payload Indexes
Upon initialization, `QdrantVectorStore.ensure_collection_exists()` configures field indexes for high-speed filtered queries:
- `tenant_id` (`keyword`)
- `document_id` (`keyword`)
- `version_id` (`keyword`)
- `user_id` (`keyword`)
- `page_number` (`integer`)
- `chunk_index` (`integer`)

---

## 5. Deterministic Point IDs & Idempotency

To prevent vector duplication during document re-processing or re-indexing, Qdrant point IDs are computed deterministically using UUIDv5:

$$\text{Point ID} = \text{UUIDv5}(\text{NAMESPACE\_DNS}, \text{f"\{version\_id\}:\{chunk\_id\}:\{model\_name\}"})$$

When re-indexing a version:
1. `delete_by_version_id(version_id)` removes old vector points from Qdrant.
2. `delete_by_chunk_ids(chunk_ids)` removes stale embedding audit rows from PostgreSQL.
3. Points are re-computed and upserted cleanly.

---

## 6. Multi-Tenant Security & Ownership Isolation

- **Search Guardrails**: Vector searches require a `tenant_id` filter. Non-admin users are strictly scoped with `user_id` filters to prevent cross-user data leakage.
- **Cascade Cleanup**: When a document is soft-deleted or permanently removed, all vector points in Qdrant and audit rows in `embedding_records` are wiped immediately.
- **Credential Protection**: Qdrant connection credentials and internal endpoints are never exposed to clients or returned in API responses.

---

## 7. Re-indexing API

### `POST /api/v1/documents/{document_id}/reindex`
Recomputes embeddings for all chunks in the document's latest version and upserts them to Qdrant.

#### Response (200 OK):
```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "version_id": "7b13df18-4444-486a-bc01-38e219714eb8",
  "status": "INDEXED",
  "chunks_indexed": 42,
  "model_name": "BAAI/bge-small-en-v1.5",
  "dimension": 384,
  "message": "Document re-indexed successfully."
}
```
