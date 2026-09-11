"""
DocuFlow AI — Application Layer Metadata Extractor.

Extracts rich business, structural, and operational metadata from parsed documents,
including titles, section hierarchies, language detection, document statistics,
provenance, and parser versions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SectionNode:
    """Represents a node in the document's section hierarchy tree."""

    title: str
    level: int
    page: int = 1
    children: list[SectionNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "level": self.level,
            "page": self.page,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class ExtractedMetadata:
    """Comprehensive document metadata container."""

    title: str
    filename: str
    file_type: str
    page_count: int
    language: str
    section_hierarchy: list[dict[str, Any]]
    table_count: int
    figure_count: int
    word_count: int
    character_count: int
    checksum: str
    processing_version: str = "1.0.0"
    parser_version: str = "docling-2.x"
    creation_date: str | None = None
    update_date: str | None = None
    custom_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetadataExtractor:
    """Application-level metadata extractor that enriches parsed documents."""

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Lightweight, fast language detector supporting common ISO 639-1 language codes."""
        if not text or len(text.strip()) < 20:
            return "en"

        sample = text[:3000].lower()

        # Stop words / distinctive particles for common languages
        patterns = {
            "en": [r"\bthe\b", r"\band\b", r"\bis\b", r"\bof\b", r"\bto\b", r"\bin\b", r"\bthat\b"],
            "es": [r"\bel\b", r"\bla\b", r"\bde\b", r"\by\b", r"\ben\b", r"\bque\b", r"\blos\b"],
            "fr": [r"\ble\b", r"\bla\b", r"\bet\b", r"\bdes\b", r"\bdu\b", r"\bdans\b", r"\bpour\b"],
            "de": [r"\bder\b", r"\bdie\b", r"\bdas\b", r"\bund\b", r"\bist\b", r"\bvon\b", r"\bmit\b"],
            "it": [r"\bil\b", r"\bla\b", r"\bdi\b", r"\be\b", r"\bper\b", r"\bsono\b", r"\bcon\b"],
            "pt": [r"\bo\b", r"\ba\b", r"\bde\b", r"\be\b", r"\bque\b", r"\bpara\b", r"\bcom\b"],
        }

        scores: dict[str, int] = {}
        for lang, regexes in patterns.items():
            count = 0
            for regex in regexes:
                count += len(re.findall(regex, sample))
            scores[lang] = count

        best_lang = max(scores, key=lambda k: scores[k])
        if scores[best_lang] > 2:
            return best_lang

        # Fallback check for CJK or Cyrillic characters
        if re.search(r"[\u4e00-\u9fff]", sample):
            return "zh"
        if re.search(r"[\u3040-\u30ff]", sample):
            return "ja"
        if re.search(r"[\u0400-\u04ff]", sample):
            return "ru"

        return "en"

    @classmethod
    def extract_section_hierarchy(cls, markdown: str) -> list[dict[str, Any]]:
        """Parse markdown heading levels (#, ##, ###) into a structured outline tree."""
        if not markdown:
            return []

        heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = heading_re.findall(markdown)

        if not matches:
            return []

        root_nodes: list[SectionNode] = []
        stack: list[SectionNode] = []

        for hashes, title in matches:
            level = len(hashes)
            clean_title = title.strip()
            node = SectionNode(title=clean_title, level=level)

            while stack and stack[-1].level >= level:
                stack.pop()

            if not stack:
                root_nodes.append(node)
            else:
                stack[-1].children.append(node)

            stack.append(node)

        return [node.to_dict() for node in root_nodes]

    @classmethod
    def extract_title(
        cls,
        markdown: str,
        filename: str,
        ast_dict: dict[str, Any] | None = None,
    ) -> str:
        """Extract the most prominent title from headings or AST, with safe filename fallback."""
        # 1. Check top-level heading in markdown
        match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                return candidate

        # 2. Check AST name or metadata if available
        if ast_dict and isinstance(ast_dict, dict):
            name = ast_dict.get("name")
            if name and isinstance(name, str) and name.strip() and name != "DoclingDocument":
                return name.strip()

        # 3. Fallback to clean filename without extension
        clean_name = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        return clean_name.title() if clean_name else "Untitled Document"

    @classmethod
    def extract(
        cls,
        markdown: str,
        plain_text: str,
        filename: str,
        file_type: str,
        checksum: str,
        page_count: int = 1,
        table_count: int = 0,
        figure_count: int = 0,
        ast_dict: dict[str, Any] | None = None,
        creation_date: str | None = None,
        update_date: str | None = None,
        custom_metadata: dict[str, Any] | None = None,
    ) -> ExtractedMetadata:
        """Extract complete normalized metadata for a document."""
        title = cls.extract_title(markdown, filename, ast_dict)
        language = cls.detect_language(plain_text)
        section_hierarchy = cls.extract_section_hierarchy(markdown)

        word_count = len(plain_text.split())
        character_count = len(plain_text)

        # Compute content checksum if not passed
        if not checksum:
            checksum = hashlib.sha256(plain_text.encode("utf-8")).hexdigest()

        return ExtractedMetadata(
            title=title,
            filename=filename,
            file_type=file_type if file_type.startswith(".") else f".{file_type}",
            page_count=max(1, page_count),
            language=language,
            section_hierarchy=section_hierarchy,
            table_count=table_count,
            figure_count=figure_count,
            word_count=word_count,
            character_count=character_count,
            checksum=checksum,
            creation_date=creation_date,
            update_date=update_date,
            custom_metadata=custom_metadata or {},
        )
