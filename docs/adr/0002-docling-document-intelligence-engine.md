# ADR 0002: Adoption of IBM Docling for Document Intelligence

**Status:** Accepted  
**Date:** 2026-09-06  
**Deciders:** Principal Software Architect, AI/ML Engineers  
**Consulted:** Backend Engineers  
**Informed:** Stakeholders  

---

## 1. Context & Problem Statement

DocuFlow AI must parse complex, heterogeneous document formats (PDF, DOCX, PPTX, XLSX, HTML, Markdown, TXT, and scanned image formats PNG, JPEG, TIFF). 

Traditional document parsing tools (such as PyPDF, pdfplumber, or Apache Tika) suffer from critical limitations:
- They extract unstructured text blobs that discard section hierarchies, headings, and lists.
- Multi-column layouts (e.g. academic papers or financial reports) are frequently read horizontally across columns, corrupting reading order.
- Tables are broken into disjointed text fragments or malformed rows.
- No unified intermediate representation exists to model layout provenance, bounding boxes, and visual elements across different file types.

We need a unified, state-of-the-art document intelligence engine capable of layout analysis, optical character recognition (OCR), table structure reconstruction, and structured semantic export.

---

## 2. Decision Drivers

- **Unified Format Support**: Native handling of PDF, Office formats (Word, Excel, PowerPoint), HTML, Markdown, and images.
- **Accurate Table Structure Extraction**: Preservation of row/column spans, headers, and cell relationships.
- **Reading Order & Layout Hierarchy**: Accurate reconstruction of multi-column reading flows and heading trees (H1 to H6).
- **Enriched Structured Representations**: Export to `DoclingDocument` JSON, normalized Markdown, and visual crops.
- **Intelligent Chunking Compatibility**: Built-in support for hierarchical chunking that respects document structure.

---

## 3. Considered Options

1. **Ad-hoc Pipeline (PyPDF + python-docx + openpyxl + pytesseract)**: Fragmented, brittle, zero cross-format unification, poor table extraction.
2. **Unstructured.io**: Comprehensive open-source library, but heavy reliance on remote cloud endpoints for advanced table extraction and complex licensing tiers.
3. **Apache Tika**: Mature and wide format support, but legacy Java-based architecture with minimal visual layout understanding and poor table parsing.
4. **IBM Docling**: Modern, open-source Python document converter with specialized AI models (TableFormer, layout vision models, EasyOCR/Tesseract integration, and native `DoclingDocument` structure).

---

## 4. Decision Outcome

**Chosen Option:** Option 4 — **IBM Docling**.

We adopt IBM Docling as the core document intelligence engine, wrapped behind a clean `DocumentParserGateway` adapter.

### Positive Consequences
- **State-of-the-Art Extraction**: Deep visual layout analysis paired with TableFormer yields unmatched table extraction fidelity.
- **Unified Document Model**: Regardless of input format (PDF, DOCX, XLSX, HTML), Docling outputs a consistent `DoclingDocument` JSON AST.
- **Seamless Hierarchical Chunking**: Docling's `HierarchicalChunker` directly traverses the parsed document tree, emitting chunks with ancestral heading breadcrumbs and bounding box metadata.
- **Direct Markdown & Asset Export**: Clean Markdown export (`export_to_markdown()`) and native image cropping for figures and tables.

### Negative Consequences
- **Resource Footprint**: Docling models (PyTorch layout models, TableFormer, OCR) require significant RAM (2–4 GB per worker) and benefit from GPU acceleration.
- **Mitigation**: Docling execution is strictly confined to asynchronous Celery parsing workers (`docuflow.parsing` queue). The main FastAPI web server never loads or runs Docling models, preventing web server memory spikes.
