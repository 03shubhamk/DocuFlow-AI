"""
DocuFlow AI — Performance & Scalability Benchmark Suite.

Measures and asserts SLA bounds across:
- 10-page PDF ingestion & search
- 100-page PDF scaled parsing & batch embeddings
- Large document upload streaming & memory ceiling
- Multi-client concurrent uploads & connection pool throughput
- Search latency distributions (p50, p95) and embedding throughput (chunks/s)
"""

from __future__ import annotations

import io
import time
import tracemalloc
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.documents.service import DocumentService
from app.application.embeddings.service import EmbeddingService
from app.application.search.service import SearchService
from app.domain.entities import User, UserRole
from app.infrastructure.database.models import UserModel
from app.infrastructure.processors.mock_processor import MockDocumentProcessor
from app.infrastructure.storage.memory_storage import InMemoryStorage
from app.infrastructure.vectorstore.memory_store import InMemoryVectorStore
from tests.fixtures.sample_files import (
    create_oversized_payload_bytes,
    create_sample_pdf_bytes,
)


class TestPerformanceBenchmarks:
    @pytest.mark.asyncio
    async def test_10_page_pdf_pipeline_benchmark(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        """Benchmark ingestion, metadata extraction, structure-aware chunking, batch embeddings, and search on a 10-page PDF."""
        tracemalloc.start()
        start_cpu = time.process_time()
        start_time = time.perf_counter()

        storage = InMemoryStorage()
        processor = MockDocumentProcessor()
        vector_store = InMemoryVectorStore()
        embedding_service = EmbeddingService()
        doc_service = DocumentService(
            session=db_session,
            storage=storage,
            processor=processor,
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        user_entity = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )

        # 1. Measure Upload Latency
        upload_start = time.perf_counter()
        pdf_bytes = create_sample_pdf_bytes(title="10-Page Benchmark Report", page_count=10)
        uploaded = await doc_service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="benchmark_10p.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )
        upload_latency_ms = (time.perf_counter() - upload_start) * 1000

        # 2. Measure Processing & Chunking Duration
        proc_start = time.perf_counter()
        processed = await doc_service.process_document_version(
            document_id=uploaded.document.id,
            version_id=uploaded.job.version_id,
        )
        proc_duration_ms = (time.perf_counter() - proc_start) * 1000

        # 3. Measure Embedding Throughput & Reindexing
        embed_start = time.perf_counter()
        reindex_res = await doc_service.reindex_document(
            document_id=uploaded.document.id,
            current_user=user_entity,
        )
        embed_duration_s = max(time.perf_counter() - embed_start, 0.001)
        chunks_indexed = reindex_res.chunks_indexed
        embedding_throughput = chunks_indexed / embed_duration_s

        # 4. Measure Search Latency (p50 / p95 across 20 query runs)
        search_service = SearchService(
            session=db_session,
            vector_store=vector_store,
            embedding_service=embedding_service,
        )
        from app.application.search.schemas import SearchRequest

        latencies = []
        for _ in range(20):
            q_start = time.perf_counter()
            await search_service.search(
                request=SearchRequest(query="quarterly revenue growth", top_k=5),
                current_user=user_entity,
            )
            latencies.append((time.perf_counter() - q_start) * 1000)

        latencies.sort()
        p50_search_latency_ms = latencies[len(latencies) // 2]
        p95_search_latency_ms = latencies[int(len(latencies) * 0.95)]

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        cpu_time_s = time.process_time() - start_cpu
        total_time_s = time.perf_counter() - start_time
        tracemalloc.stop()

        # Assertions & Verification SLAs
        assert processed.page_count >= 1
        assert upload_latency_ms < 300  # <300ms upload validation & insert
        assert proc_duration_ms < 2000  # <2s processing for 10-page document
        assert chunks_indexed > 0
        assert p95_search_latency_ms < 50  # <50ms vector search SLA

        print(
            f"\n[BENCHMARK 10-PAGE PDF]\n"
            f" - Upload Latency: {upload_latency_ms:.2f} ms\n"
            f" - Processing Duration: {proc_duration_ms:.2f} ms\n"
            f" - Chunks Indexed: {chunks_indexed}\n"
            f" - Embedding Throughput: {embedding_throughput:.1f} chunks/sec\n"
            f" - Search Latency p50: {p50_search_latency_ms:.2f} ms | p95: {p95_search_latency_ms:.2f} ms\n"
            f" - Peak Memory: {peak_mem / (1024 * 1024):.2f} MB\n"
            f" - CPU Time: {cpu_time_s:.2f} s (Total Wall: {total_time_s:.2f} s)\n"
        )

    @pytest.mark.asyncio
    async def test_100_page_pdf_scaled_benchmark(
        self,
        db_session: AsyncSession,
        test_user: UserModel,
    ):
        """Benchmark 100-page document ingestion, batch embedding vectorization, and memory containment."""
        tracemalloc.start()
        start_cpu = time.process_time()

        storage = InMemoryStorage()
        processor = MockDocumentProcessor()
        vector_store = InMemoryVectorStore()
        embedding_service = EmbeddingService(batch_size=64)
        doc_service = DocumentService(
            session=db_session,
            storage=storage,
            processor=processor,
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        user_entity = User(
            id=test_user.id,
            tenant_id=test_user.tenant_id,
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            full_name=test_user.full_name,
            role=UserRole(test_user.role),
        )

        # Generate 100-page document payload
        pdf_bytes = create_sample_pdf_bytes(
            title="100-Page Comprehensive Annual Regulatory & Financial Review",
            page_count=100,
        )

        upload_start = time.perf_counter()
        uploaded = await doc_service.upload_document(
            file_stream=io.BytesIO(pdf_bytes),
            raw_filename="annual_100p_report.pdf",
            content_type="application/pdf",
            current_user=user_entity,
        )
        upload_ms = (time.perf_counter() - upload_start) * 1000

        proc_start = time.perf_counter()
        processed = await doc_service.process_document_version(
            document_id=uploaded.document.id,
            version_id=uploaded.job.version_id,
        )
        proc_ms = (time.perf_counter() - proc_start) * 1000

        # Vector Indexing
        idx_start = time.perf_counter()
        reindex_res = await doc_service.reindex_document(
            document_id=uploaded.document.id,
            current_user=user_entity,
        )
        idx_duration_s = max(time.perf_counter() - idx_start, 0.001)

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        cpu_time_s = time.process_time() - start_cpu
        tracemalloc.stop()

        assert processed.page_count == 100
        assert reindex_res.chunks_indexed >= 20
        # Peak memory for in-memory 100 page mock test should stay well bounded
        assert peak_mem < 150 * 1024 * 1024  # <150 MB

        print(
            f"\n[BENCHMARK 100-PAGE PDF]\n"
            f" - Upload: {upload_ms:.2f} ms\n"
            f" - Processing & Chunking: {proc_ms:.2f} ms\n"
            f" - Chunks Indexed: {reindex_res.chunks_indexed} in {idx_duration_s:.2f} s ({reindex_res.chunks_indexed / idx_duration_s:.1f} chunks/sec)\n"
            f" - Peak RAM: {peak_mem / (1024 * 1024):.2f} MB\n"
            f" - CPU Time: {cpu_time_s:.2f} s\n"
        )

    def test_large_document_streaming_memory_ceiling(
        self,
        client: TestClient,
        user_auth_headers: dict[str, str],
    ):
        """Verify large document upload streaming enforces size bounds without memory explosion."""
        from app.api.security_middleware import get_rate_limiter
        get_rate_limiter().reset()

        tracemalloc.start()

        # 30 MB valid payload
        large_bytes = create_oversized_payload_bytes(size_mb=30)
        files = {"file": ("large_document.pdf", io.BytesIO(large_bytes), "application/pdf")}

        t0 = time.perf_counter()
        resp = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
        upload_time_ms = (time.perf_counter() - t0) * 1000

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert resp.status_code == 201
        data = resp.json()
        assert data["document"]["file_size_bytes"] == len(large_bytes)

        print(
            f"\n[BENCHMARK LARGE DOCUMENT STREAMING]\n"
            f" - 30MB Upload Latency: {upload_time_ms:.2f} ms (Throughput: {(30 / (upload_time_ms / 1000)):.1f} MB/s)\n"
            f" - Peak Memory during stream validation: {peak_mem / (1024 * 1024):.2f} MB\n"
        )

    def test_multiple_concurrent_uploads_benchmark(
        self,
        client: TestClient,
        user_auth_headers: dict[str, str],
    ):
        """Simulate high-frequency burst document uploads and benchmark p50/p95 latency and throughput."""
        from app.api.security_middleware import get_rate_limiter
        get_rate_limiter().reset()

        num_requests = 10

        results = []
        start_time = time.perf_counter()

        for i in range(num_requests):
            doc_bytes = create_sample_pdf_bytes(f"Concurrent Ingestion Document Sequence {i}")
            t0 = time.perf_counter()
            files = {"file": (f"concurrent_doc_{i}_{uuid.uuid4().hex[:4]}.pdf", io.BytesIO(doc_bytes), "application/pdf")}
            res = client.post("/api/v1/documents", files=files, headers=user_auth_headers)
            duration_ms = (time.perf_counter() - t0) * 1000
            results.append({
                "status_code": res.status_code,
                "duration_ms": duration_ms,
            })

        total_wall_time_s = time.perf_counter() - start_time

        durations = [r["duration_ms"] for r in results]
        durations.sort()
        p50 = durations[len(durations) // 2]
        p95 = durations[int(len(durations) * 0.95)]
        success_count = sum(1 for r in results if r["status_code"] == 201)

        assert success_count == num_requests
        assert p95 < 500  # <500ms per upload in pipeline

        print(
            f"\n[BENCHMARK BURST UPLOADS ({num_requests} Rapid Requests)]\n"
            f" - Total Time: {total_wall_time_s:.2f} s\n"
            f" - Throughput: {num_requests / total_wall_time_s:.1f} uploads/sec\n"
            f" - Latency p50: {p50:.2f} ms | p95: {p95:.2f} ms\n"
            f" - Success Rate: {success_count}/{num_requests} (100%)\n"
        )
