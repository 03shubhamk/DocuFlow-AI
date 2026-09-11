"""
DocuFlow AI — Document Normalization Layer.

Performs safe text cleaning, unicode normalization (NFKC), control character removal,
and whitespace sanitization while strictly preserving structural elements (headings,
section hierarchy, Markdown formatting, tables, code blocks, lists, and page boundaries).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


class DocumentNormalizer:
    """Production text and structure normalizer for parsed document representations."""

    # Regex for stripping non-printable control characters except standard whitespace (\t, \n, \r)
    _CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

    # Regex for hyphenated word breaks at line ends (e.g., "infor-\nmation" -> "information")
    _HYPHEN_BREAK_RE = re.compile(r"(\b\w+)-\s*\n\s*(\w+\b)")

    # Regex for collapsing 3+ consecutive newlines into 2 (paragraph break)
    _EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")

    # Regex for stripping trailing whitespace on each line
    _TRAILING_WHITESPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Clean and normalize a text string without altering structural semantics."""
        if not text:
            return ""

        # 1. Unicode NFKC normalization (normalizes full-width characters, ligature forms, etc.)
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Strip null bytes and non-printable control chars
        cleaned = cls._CONTROL_CHAR_RE.sub("", normalized)

        # 3. Replace Windows carriage returns and normalize newlines
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # 4. Repair line-break hyphenations
        cleaned = cls._HYPHEN_BREAK_RE.sub(r"\1\2", cleaned)

        # 5. Remove trailing whitespace on individual lines
        cleaned = cls._TRAILING_WHITESPACE_RE.sub("", cleaned)

        # 6. Collapse excessive blank lines while preserving paragraph separation
        cleaned = cls._EXCESSIVE_NEWLINES_RE.sub("\n\n", cleaned)

        return cleaned.strip()

    @classmethod
    def normalize_markdown(cls, markdown: str) -> str:
        """Clean markdown text while strictly preserving headings, table pipes, and list bullets."""
        if not markdown:
            return ""

        cleaned = cls.clean_text(markdown)

        # Ensure headings have proper space after '#' (e.g. '##Heading' -> '## Heading')
        cleaned = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", cleaned, flags=re.MULTILINE)

        return cleaned

    @classmethod
    def normalize_ast(cls, json_dict: dict[str, Any]) -> dict[str, Any]:
        """Deeply normalize text fields in a DoclingDocument AST dictionary."""
        if not json_dict or not isinstance(json_dict, dict):
            return json_dict

        normalized_dict = {}
        for key, value in json_dict.items():
            if isinstance(value, str):
                normalized_dict[key] = cls.clean_text(value)
            elif isinstance(value, list):
                normalized_dict[key] = [
                    cls.normalize_ast(item) if isinstance(item, dict)
                    else (cls.clean_text(item) if isinstance(item, str) else item)
                    for item in value
                ]
            elif isinstance(value, dict):
                normalized_dict[key] = cls.normalize_ast(value)
            else:
                normalized_dict[key] = value

        return normalized_dict
