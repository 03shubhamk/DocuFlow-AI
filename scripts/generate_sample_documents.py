"""
DocuFlow AI — Sample Document Generator.

Generates realistic test documents (PDF, Markdown, TXT) for testing layout extraction,
table parsing, OCR, and hybrid search in DocuFlow AI.
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

OUT_DIR = Path(__file__).resolve().parent.parent / "sample_documents"
OUT_DIR.mkdir(exist_ok=True)


def generate_pdf():
    pdf_path = OUT_DIR / "Enterprise_AI_Strategy_2026.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading2"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#4338ca"),
        spaceBefore=14,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading3"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("Enterprise Document Intelligence Strategy 2026", title_style))
    story.append(Paragraph("<b>Author:</b> Global Data & AI Architecture Team &bull; <b>Classification:</b> Confidential", body_style))
    story.append(Spacer(1, 12))

    # Section 1
    story.append(Paragraph("1. Executive Summary", h1_style))
    story.append(Paragraph(
        "This strategic document outlines the deployment of unified document intelligence, "
        "hierarchical AST chunking, and reciprocal rank fusion search across multi-tenant enterprise repositories. "
        "Our objective is to reduce manual contract review times by 65% and achieve sub-50ms hybrid retrieval latencies.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    # Section 2
    story.append(Paragraph("2. Financial Performance & Projection Matrix", h1_style))
    story.append(Paragraph("The table below details quarterly infrastructure cost optimizations and projected operational return on investment (ROI).", body_style))
    story.append(Spacer(1, 6))

    # Table
    table_data = [
        ["Quarter", "Ingestion Volume (Docs)", "Avg Latency (s)", "Cost Savings ($)", "Accuracy Rate"],
        ["Q1 2026", "250,000", "1.42s", "$140,000", "98.2%"],
        ["Q2 2026", "480,000", "1.18s", "$290,000", "99.1%"],
        ["Q3 2026 (Target)", "850,000", "0.95s", "$520,000", "99.6%"],
        ["Q4 2026 (Projected)", "1,500,000", "0.82s", "$950,000", "99.8%"],
    ]

    t = Table(table_data, colWidths=[100, 120, 90, 100, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#ffffff")]),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Section 3
    story.append(Paragraph("3. Architectural Pillars", h1_style))
    story.append(Paragraph("3.1 Document Parsing with IBM Docling 2.x", h2_style))
    story.append(Paragraph(
        "By migrating from legacy rule-based OCR to IBM Docling 2.x Unified AST models, DocuFlow preserves "
        "complex tabular structures, multi-level headings, bounding boxes, and embedded charts without data loss.",
        body_style,
    ))

    story.append(Paragraph("3.2 Dense + Sparse Vector Search Fusion", h2_style))
    story.append(Paragraph(
        "Semantic similarity embeddings generated via BAAI/bge-small-en-v1.5 FastEmbed models are combined "
        "with sparse BM25 lexical rank weights using Reciprocal Rank Fusion (RRF, constant k=60).",
        body_style,
    ))

    story.append(PageBreak())

    # Page 2: Risk and Governance
    story.append(Paragraph("4. Enterprise Security & Multi-Tenant Isolation", h1_style))
    story.append(Paragraph(
        "Every document asset, chunk index, and query context enforces strict cryptographic tenant scoping. "
        "Insecure direct object reference (IDOR) vulnerabilities are eliminated through ownership checks at the API, "
        "PostgreSQL database, and Qdrant payload collection filter layers.",
        body_style,
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. Risk Mitigation & Disaster Recovery", h1_style))
    story.append(Paragraph(
        "&bull; <b>Recovery Point Objective (RPO):</b> Less than 5 minutes via continuous WAL archiving.<br/>"
        "&bull; <b>Recovery Time Objective (RTO):</b> Less than 15 minutes with automated container failover.<br/>"
        "&bull; <b>Malware Protection:</b> Streaming magic-byte inspection and EICAR binary signature detection.",
        body_style,
    ))

    doc.build(story)
    print(f"Generated: {pdf_path}")


def generate_markdown():
    md_path = OUT_DIR / "Q3_Financial_Performance.md"
    content = """# DocuFlow Financial Performance & Operations Report — Q3 2026

## 1. Overview & Revenue Metrics

During the third quarter of 2026, DocuFlow AI demonstrated strong performance across all document intelligence metrics.

### Revenue Summary Table

| Business Unit | Q2 2026 Actual | Q3 2026 Target | Q3 2026 Actual | YoY Growth |
| :--- | :--- | :--- | :--- | :--- |
| **Enterprise Subscriptions** | $2.4M | $2.8M | **$3.1M** | +42% |
| **Document API Ingestion** | $850K | $920K | **$1.05M** | +55% |
| **On-Premises Dedicated Nodes** | $600K | $650K | **$720K** | +28% |
| **Total Revenue** | $3.85M | $4.37M | **$4.87M** | **+44%** |

---

## 2. Infrastructure Latency & SLA Guarantees

* **Average Document Processing Time:** 1.15 seconds per 20-page PDF.
* **Vector Search Latency:** 24ms p95, 38ms p99 across 5,000,000 indexed chunks.
* **Uptime Compliance:** 99.98% availability against a 99.95% SLA target.

---

## 3. Compliance and Legal Obligations

1. **Data Retention Policy:** Documents marked for soft-deletion are expunged from MinIO object storage after a 30-day grace period.
2. **Audit Trails:** All user logins, document views, chunk searches, and exports are immutably logged to the `audit_logs` table.
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {md_path}")


def generate_contract_txt():
    txt_path = OUT_DIR / "Cloud_Architecture_Contract.txt"
    content = """MASTER SERVICE AGREEMENT & LEVEL AGREEMENT (SLA)

BETWEEN: DocuFlow AI Cloud Technologies Inc. ("Provider")
AND: Global Enterprise Solutions Corp. ("Customer")
EFFECTIVE DATE: September 1, 2026

1. SCOPE OF SERVICES
Provider agrees to deliver AI document intelligence, OCR layout analysis, hierarchical chunking,
and hybrid vector search infrastructure hosted on dedicated multi-tenant Kubernetes clusters.

2. SERVICE LEVEL OBJECTIVES (SLO)
2.1 Service Availability: Provider guarantees 99.95% uptime during each calendar billing cycle.
2.2 Query Response Time: 95% of semantic hybrid search queries shall complete in under 50 milliseconds.
2.3 Batch Ingestion Throughput: The platform supports concurrent ingestion of up to 500 documents per minute.

3. PENALTIES AND TERMINATION CLAUSE
In the event that monthly service availability falls below 99.90%, Customer is entitled to a 15% billing credit.
If availability drops below 99.00%, Customer may terminate this agreement with written notice within 14 days
without incurring early termination penalties.

4. CONFIDENTIALITY AND DATA ISOLATION
All customer document embeddings, extracted text, and relational metadata remain the exclusive property of Customer.
Provider guarantees logical vector collection separation and zero cross-tenant query leakage.
"""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {txt_path}")


if __name__ == "__main__":
    generate_pdf()
    generate_markdown()
    generate_contract_txt()
    print("\nAll sample documents generated successfully in 'sample_documents/' directory!")
