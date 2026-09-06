# ADR 0004: Qdrant for Vector Embeddings and Hybrid Search

**Status:** Accepted  
**Date:** 2026-09-06  
**Deciders:** Principal Software Architect, Search Engineers  
**Consulted:** Backend Team  
**Informed:** Stakeholders  

---

## 1. Context & Problem Statement

DocuFlow AI requires a vector database capable of indexing millions of document text chunks, supporting low-latency (< 50ms) similarity search, enforcing strict multi-tenant isolation, and handling both semantic intent and exact keyword matches.

Documents frequently contain alphanumeric part numbers, legal clause citations, or specific financial metrics where pure dense semantic search suffers from "fuzzy" false positives. Conversely, standard lexical BM25 search fails to capture semantic concepts and synonyms.

We require a vector database that provides:
1. High-throughput dense vector indexing (HNSW).
2. Native payload filtering to enforce tenant boundaries without query performance penalties.
3. Hybrid search capabilities combining dense semantic vectors with lexical sparse matching.
4. Flexible hosting (single Docker container for local dev, distributed cluster for production).

---

## 2. Decision Drivers

- **Multi-Tenant Security**: Ability to filter vector queries by `tenant_id` at index time without degrading recall or latency.
- **Hybrid Retrieval**: Native dense vector similarity + sparse lexical/keyword scoring.
- **Resource Efficiency**: On-disk payload storage and memory-mapped vectors to prevent RAM exhaustion.
- **Operational Simplicity**: Clean Python SDK (`qdrant-client`), robust snapshot API, and simple container deployment.

---

## 3. Considered Options

1. **PostgreSQL with `pgvector`**: Convenient since PostgreSQL is already in the stack, but HNSW index build times are slow, memory consumption is high for large datasets, and hybrid sparse vector search is complex to tune alongside relational workloads.
2. **Pinecone**: Fully managed, but proprietary SaaS-only, preventing offline local development and posing compliance challenges for air-gapped on-premise deployments.
3. **Milvus**: Powerful for massive scale, but complex distributed architecture (requires Etcd, Pulsar/Kafka, MinIO) with heavy operational overhead.
4. **Qdrant**: High-performance vector search engine written in Rust, featuring native payload filtering, hybrid dense/sparse search, memory-mapped storage, single-binary Docker deployment, and enterprise cloud availability.

---

## 4. Decision Outcome

**Chosen Option:** Option 4 — **Qdrant**.

We adopt Qdrant as the dedicated vector storage and search engine for DocuFlow AI, isolated behind the `VectorStoreGateway` port in the Domain layer.

### Positive Consequences
- **Strict Multi-Tenant Filtering**: Qdrant applies payload filters *during* the graph traversal phase (payload-aware HNSW), guaranteeing 100% precision and zero cross-tenant leakage.
- **Hybrid Search**: Supports dense vector cosine similarity alongside sparse BM25 vectors, providing optimal search relevance for both conceptual questions and exact keyword lookups.
- **Fast Local & Cloud Deployment**: Runs as a lightweight Docker container locally (`qdrant/qdrant:latest`) and scales into a distributed cluster with replication in production.
- **Snapshot Backups**: Provides a native HTTP snapshot API for point-in-time collection backups directly to S3.

### Negative Consequences
- **Additional Service to Manage**: Requires running and monitoring Qdrant alongside PostgreSQL.
- **Dual Persistence Consistency**: Chunks exist in both PostgreSQL (for relational integrity) and Qdrant (for vector search).
- **Mitigation**: An atomic indexing task updates PostgreSQL and Qdrant in tandem. When a document is deleted, a background task purges its points from Qdrant using the `delete(filter={"document_id": ...})` API.
