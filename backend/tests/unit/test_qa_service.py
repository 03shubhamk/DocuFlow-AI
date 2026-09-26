"""
DocuFlow AI — Unit Tests for Generative Q&A and Chat Service.
"""

import uuid
import pytest
from app.application.search.qa_service import QAService
from app.application.search.schemas import SearchResultItem, ChatMessage


@pytest.fixture
def qa_service() -> QAService:
    return QAService()


@pytest.fixture
def sample_results() -> list[SearchResultItem]:
    doc_id = uuid.uuid4()
    return [
        SearchResultItem(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_name="Enterprise_Cloud_Strategy.pdf",
            score=0.92,
            text="Cloud computing provides scalable infrastructure on demand. Infrastructure as a Service (IaaS) enables flexible virtual machine hosting.",
            page_number=1,
            page_numbers=[1],
            heading_hierarchy=["Executive Summary", "Cloud Foundations"],
            section="Cloud Foundations",
            chunk_index=0,
            metadata={},
        ),
        SearchResultItem(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_name="Enterprise_Cloud_Strategy.pdf",
            score=0.85,
            text="Security and compliance are mandatory for all multi-tenant deployments.",
            page_number=2,
            page_numbers=[2],
            heading_hierarchy=["Security Architecture"],
            section="Security Architecture",
            chunk_index=1,
            metadata={},
        ),
    ]


def test_generate_answer_with_empty_results(qa_service: QAService):
    res = qa_service.generate_answer("What is cloud computing?", [])
    assert res.confidence == 0.0
    assert len(res.citations) == 0
    assert "No relevant content found" in res.answer


def test_generate_answer_with_results(qa_service: QAService, sample_results: list[SearchResultItem]):
    res = qa_service.generate_answer("What is cloud computing?", sample_results)
    assert res.confidence > 0.8
    assert len(res.citations) == 2
    assert res.citations[0].document_name == "Enterprise_Cloud_Strategy.pdf"
    assert res.citations[0].citation_id == 1
    assert "Enterprise_Cloud_Strategy.pdf" in res.answer


def test_generate_chat_response(qa_service: QAService, sample_results: list[SearchResultItem]):
    messages = [
        ChatMessage(role="user", content="Explain cloud computing services"),
    ]
    chat_res = qa_service.generate_chat_response(messages, sample_results)
    assert chat_res.confidence > 0.8
    assert len(chat_res.citations) == 2
    assert "Enterprise_Cloud_Strategy.pdf" in chat_res.message
