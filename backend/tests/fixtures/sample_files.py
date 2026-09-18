"""
DocuFlow AI — Deterministic Test File Generators and Fixtures.

Provides valid and invalid file payloads (PDFs, Markdown, text, archives, executables)
without external network or filesystem dependencies.
"""

from __future__ import annotations

import io
import zipfile


def create_sample_pdf_bytes(
    title: str = "DocuFlow AI Report",
    text_content: str = "Enterprise Document Intelligence Platform",
    page_count: int = 1,
) -> bytes:
    """Generate a valid, minimal, deterministic PDF file binary with configurable page count."""
    page_objects = []
    kids = []
    current_obj = 3

    for i in range(page_count):
        kids.append(f"{current_obj} 0 R")
        page_objects.append(
            f"""{current_obj} 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {current_obj + 1} 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
{current_obj + 1} 0 obj
<< /Length 120 >>
stream
BT
/F1 12 Tf
72 712 Td
({title} - Page {i + 1}: {text_content}) Tj
ET
endstream
endobj"""
        )
        current_obj += 2

    kids_str = " ".join(kids)
    pages_body = "\n".join(page_objects)

    content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [{kids_str}] /Count {page_count} >>
endobj
{pages_body}
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
trailer
<< /Size {current_obj + 2} /Root 1 0 R >>
startxref
464
%%EOF"""
    return content.encode("utf-8")


def create_sample_markdown_bytes(title: str = "Architecture Overview", body: str = "DocuFlow AI handles intelligent chunking and hybrid vector search.") -> bytes:
    """Generate a deterministic Markdown document binary."""
    md = f"""# {title}

## Introduction
{body}

### Key Specifications
- Chunk Size: 512 tokens
- Overlap: 64 tokens
- Provider: FastEmbed BAAI/bge-small-en-v1.5

| Metric | Target |
| :--- | :--- |
| p95 Query Latency | < 50ms |
| Chunk Precision | 99.4% |
"""
    return md.encode("utf-8")


def create_sample_text_bytes(content: str = "Standard plain text payload for DocuFlow validation.") -> bytes:
    """Generate a deterministic plain text document binary."""
    return content.encode("utf-8")


def create_corrupted_pdf_bytes() -> bytes:
    """Generate a corrupted PDF file (invalid magic bytes and truncated header)."""
    return b"%PDF-INVALID\x00\xff\xfeTRUNCATED_CORRUPTED_FILE_DATA_12345"


def create_oversized_payload_bytes(size_mb: int = 55, valid_pdf_header: bool = True) -> bytes:
    """Generate an oversized byte array exceeding or reaching a specific MB size with valid magic bytes."""
    header = b"%PDF-1.4\n%DocuFlow Large Payload\n" if valid_pdf_header else b""
    padding_needed = max(0, (size_mb * 1024 * 1024) - len(header))
    return header + (b"0" * padding_needed)


def create_fake_windows_executable_bytes() -> bytes:
    """Generate a binary starting with Windows PE MZ magic bytes disguised as a document."""
    return b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00FAKE_WINDOWS_EXECUTABLE"


def create_fake_linux_elf_bytes() -> bytes:
    """Generate a binary starting with Linux ELF magic bytes disguised as a document."""
    return b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00FAKE_LINUX_BINARY"


def create_valid_docx_bytes() -> bytes:
    """Generate a valid minimal Word (.docx) OOXML zip archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        zf.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DocuFlow Document Content</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def create_malicious_path_traversal_zip_bytes() -> bytes:
    """Generate a zip archive with directory traversal filename."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
    return buf.getvalue()
