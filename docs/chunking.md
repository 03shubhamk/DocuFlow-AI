# Intelligent Chunking & Normalization Architecture

## 1. Overview

Phase 5 implements a structure-preserving document normalization, metadata extraction, and intelligent chunking pipeline. It takes the parsed representations (`DoclingDocument` AST and Markdown) produced by Phase 4 and generates deterministic, enriched `DocumentChunk` records stored in PostgreSQL and exported to MinIO/S3.

```
DoclingDocument AST & Markdown
             ↓
    DocumentNormalizer
  (NFKC, control char stripping, structural preservation)
             ↓
     MetadataExtractor
  (Title, Outline Tree, Language, Statistics)
             ↓
 Intelligent Chunker Engine
  (Hierarchical | Hybrid | Sliding Window)
             ↓
   DocumentChunk Records
  ├── PostgreSQL (document_chunks table)
  └── MinIO/S3 (chunks.json artifact)
```

---

## 2. Document Normalization

The normalization layer cleans text anomalies without altering or destroying the document's semantic and Markdown structure.

### Normalization Rules
1. **Unicode NFKC Normalization**: Converts non-standard full-width characters and ligature forms into canonical Unicode equivalents (`unicodedata.normalize("NFKC", text)`).
2. **Control Character Stripping**: Strips null bytes (`\x00`) and non-printable control characters while preserving standard formatting whitespace (`\t`, `\n`, `\r`).
3. **Hyphenation Repair**: Merges broken word breaks at line ends (e.g., `infor-\nmation` $\to$ `information`).
4. **Whitespace Consolidation**: Collapses 3+ consecutive blank lines into standard paragraph delimiters (`\n\n`) and strips trailing whitespace from individual lines.
5. **Structural Integrity**: Strictly preserves Markdown heading syntax (`#`, `##`), table delimiters (`|`), list markers, code fences, and page markers.

---

## 3. Application-Level Metadata Extraction

Rather than relying solely on raw parser output, DocuFlow AI extracts enriched business and structural metadata in the application layer:

| Field | Type | Description |
|---|---|---|
| `title` | `string` | Extracted title from top-level heading (`# Title`), AST metadata, or clean filename fallback. |
| `filename` | `string` | Original uploaded filename. |
| `file_type` | `string` | File extension (e.g., `.pdf`, `.docx`). |
| `page_count` | `integer` | Total number of pages in the source document. |
| `language` | `string` | Detected ISO 639-1 language code (e.g., `en`, `es`, `fr`, `de`, `zh`, `ja`). |
| `section_hierarchy` | `array` | Hierarchical outline tree representing nested headings and section levels. |
| `table_count` | `integer` | Total number of tables identified in the document. |
| `figure_count` | `integer` | Total number of figures/images extracted. |
| `word_count` | `integer` | Word count of cleaned plain text. |
| `character_count` | `integer` | Character count of cleaned plain text. |
| `checksum` | `string` | SHA-256 content checksum. |
| `processing_version`| `string` | `"1.0.0"` pipeline version. |
| `parser_version` | `string` | `"docling-2.x"` backend parser identifier. |

---

## 4. Chunking Strategies

DocuFlow AI provides two primary configurable chunking strategies:

### 4.1 Hierarchical / Structure-Aware Chunking (`"hierarchical"`)
- **Heading Hierarchy Tracking**: Maintains an active heading stack (e.g., `["Architecture", "Storage Layer", "MinIO"]`).
- **Section Path**: Encodes full context in `section_path` (e.g., `"Architecture > Storage Layer > MinIO"`).
- **Paragraph Grouping**: Groups coherent paragraphs under the current section up to `CHUNK_MAX_TOKENS`.
- **Table Preservation**:
  - Small and medium tables (within `CHUNK_MAX_TOKENS`) are kept intact as single atomic chunks.
  - Large tables exceeding `CHUNK_MAX_TOKENS` are split row-wise while replicating table header rows on each sub-chunk.
- **Page Number Tracking**: Chunks record all page numbers they span (`page_numbers: [1, 2]`).

### 4.2 Hybrid Chunking (`"hybrid"`)
- Combines hierarchical boundary awareness with sliding-window token overlap (`CHUNK_OVERLAP_TOKENS`).
- Injects a contextual prefix `[... {previous_snippet}]` from preceding chunks sharing the same section hierarchy to maximize retrieval recall and LLM context coverage.

---

## 5. Chunk Structure & PostgreSQL Schema

Each chunk is stored in PostgreSQL in the `document_chunks` table:

```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    heading_hierarchy JSONB NOT NULL DEFAULT '[]',
    page_numbers INTEGER[] NOT NULL DEFAULT '{}',
    chunk_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_chunk_version_index UNIQUE (version_id, chunk_index)
);
```

### Chunk Payload Attributes
- `chunk_id`: Deterministic UUID generated via `uuid.uuid5(NAMESPACE_DNS, f"{version_id}:{chunk_index}:{checksum}")`.
- `document_id`: UUID of parent document.
- `version_id`: UUID of document version snapshot.
- `chunk_index`: 0-indexed sequential position.
- `content`: Chunk text with preserved Markdown and structure.
- `token_count`: Accurate token count computed via `tiktoken` (`cl100k_base`).
- `heading_hierarchy`: Ordered list of parent headings.
- `page_numbers`: List of 1-indexed page numbers spanned by the chunk.
- `chunk_metadata`: JSON dictionary containing `checksum`, `section_path`, `source_document`, and `strategy`.
- `checksum`: SHA-256 digest of chunk content.

---

## 6. Determinism & Idempotency

When a document version is re-processed:
1. Prior `document_chunks` for that `version_id` are deleted from PostgreSQL (`DocumentChunkRepository.delete_by_version`).
2. New chunks are bulk-inserted with identical deterministic UUIDs and indices.
3. Derivative storage artifact `chunks.json` is updated in MinIO/S3 under `{tenant_id}/{document_id}/v{version}/artifacts/chunks.json`.
4. No duplicate records or orphaned foreign key references are left behind.

---

## 7. API Endpoints

### Retrieve Document Chunks
`GET /api/v1/documents/{document_id}/chunks`

#### Query Parameters:
- `version_id` (optional): Filter chunks by version UUID (defaults to latest version).
- `page` (optional, default: `1`): Page number.
- `page_size` (optional, default: `50`, max: `200`): Chunks per page.

#### Response Example:
```json
{
  "items": [
    {
      "id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
      "document_id": "123e4567-e89b-12d3-a456-426614174000",
      "version_id": "234e5678-e89b-12d3-a456-426614174001",
      "chunk_index": 0,
      "content": "# Architecture Overview\n\nDocuFlow AI provides end-to-end document intelligence...",
      "token_count": 84,
      "heading_hierarchy": ["Architecture Overview"],
      "page_numbers": [1],
      "chunk_metadata": {
        "section_path": "Architecture Overview",
        "checksum": "a1b2c3d4e5f6...",
        "strategy": "hierarchical"
      },
      "created_at": "2026-09-11T14:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```
