# Document Search & Retrieval Architecture

## 1. Overview

Phase 7 implements a multi-tenant, high-performance document search and retrieval engine for DocuFlow AI. It enables semantic vector search and hybrid retrieval across document chunks, combining dense vector embeddings with sparse lexical relevance (BM25 token matching) using Reciprocal Rank Fusion (RRF).

```
Client Search Request (POST /api/v1/search)
                    ↓
             SearchService
  ├── Tenant Validation & Multi-Tenant Scoping (Admin vs. User ownership)
  ├── Dense Query Embedding Generation (EmbeddingService)
  └── Strategy Dispatcher
        ├── DenseSearchStrategy (Qdrant VectorStore Cosine Similarity)
        └── HybridSearchStrategy (Dense + Sparse Lexical RRF Fusion)
                    ↓
           Qdrant / VectorStore
  ├── Payload Filters (tenant_id, user_id, document_ids, page_number)
  └── Score Threshold Filtering (e.g. score >= 0.70)
                    ↓
        Ranked SearchResponse
  ├── chunk_id, document_id, document_name, score
  ├── text, page_number, section, metadata
  └── execution duration (duration_ms) & strategy_used
```

---

## 2. Search Request & Response Specification

### `POST /api/v1/search`

#### Request Payload:
```json
{
  "query": "What are the quarterly operating margins and EBITDA targets?",
  "top_k": 10,
  "document_ids": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "page": 1,
  "filters": {
    "mime_type": ".pdf"
  },
  "score_threshold": 0.5,
  "strategy": "dense"
}
```

#### Response (200 OK):
```json
{
  "results": [
    {
      "chunk_id": "8aa64e81-b518-4b72-97fc-112233445566",
      "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "document_name": "quarterly_financials.pdf",
      "score": 0.8924,
      "text": "In Q3 2026, operating margin expanded by 140 bps to 24.8%...",
      "page_number": 1,
      "page_numbers": [1],
      "section": "Financial Overview > Operating Margins",
      "heading_hierarchy": ["Financial Overview", "Operating Margins"],
      "chunk_index": 2,
      "metadata": {
        "token_count": 84,
        "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      }
    }
  ],
  "total": 1,
  "query": "What are the quarterly operating margins and EBITDA targets?",
  "top_k": 10,
  "page": null,
  "page_size": null,
  "strategy_used": "dense",
  "duration_ms": 14.8
}
```

---

## 3. Retrieval Strategies

DocuFlow AI provides a clean strategy pattern decoupling retrieval mechanics from API routing:

### A. `DenseSearchStrategy` (Default)
- Computes dense cosine similarity between the natural language query embedding and indexed vector points in Qdrant.
- Best suited for conceptual matching, semantic similarity, paraphrased queries, and multilingual meaning.

### B. `HybridSearchStrategy` (Configurable)
- Combines dense vector similarity with sparse lexical token relevance (BM25-style frequency scoring).
- Uses Reciprocal Rank Fusion (RRF) with configurable dense and sparse weights:
  $$\text{RRF}(d) = \frac{w_{\text{dense}}}{60 + r_{\text{dense}}(d)} + \frac{w_{\text{sparse}}}{60 + r_{\text{sparse}}(d)}$$
- Ideal for queries containing exact acronyms, part numbers, SKU codes, legal citations, or specific numerical values.
- Enabled globally via `SEARCH_HYBRID_ENABLED=true` or on a per-request basis with `"strategy": "hybrid"`.

---

## 4. Multi-Tenant Security & Ownership Scoping

1. **Tenant Isolation**: Every search query strictly injects a `tenant_id` filter into Qdrant vector store queries.
2. **User Ownership**:
   - `ADMIN` users can search all documents belonging to their tenant.
   - `USER` role accounts are strictly restricted to searching chunks belonging to their own documents (`user_id = current_user.id`).
3. **Explicit Document ID Verification**: When `document_ids` are supplied in the search request, the application layer verifies tenant and ownership accessibility before issuing vector store queries.

---

## 5. Document Structure API

### `GET /api/v1/documents/{document_id}/structure`
Returns the hierarchical section outline tree, page count, and structural metadata extracted during the Docling normalization and metadata extraction phase.

#### Response:
```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "version_id": "7b13df18-4444-486a-bc01-38e219714eb8",
  "title": "Annual Performance Report",
  "original_filename": "report.pdf",
  "file_type": ".pdf",
  "page_count": 12,
  "chunk_count": 48,
  "language": "en",
  "table_count": 4,
  "figure_count": 2,
  "section_hierarchy": [
    {
      "title": "1. Executive Summary",
      "level": 1,
      "page": 1,
      "children": [
        {
          "title": "1.1 Key Achievements",
          "level": 2,
          "page": 1,
          "children": []
        }
      ]
    }
  ]
}
```
