"""
DocuFlow AI — Token Counter & Token-Aware Text Utilities.

Provides high-performance token counting using tiktoken (cl100k_base / OpenAI & modern LLMs)
with robust fallback estimation if tokenizer backend is unavailable.
"""

from __future__ import annotations

import math
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TokenCounter:
    """Token counting and token-boundary text manipulation."""

    _encoding: Any = None
    _initialized: bool = False

    @classmethod
    def _get_encoding(cls) -> Any:
        if not cls._initialized:
            try:
                import tiktoken

                cls._encoding = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning("tiktoken_init_fallback", error=str(e))
                cls._encoding = None
            cls._initialized = True
        return cls._encoding

    @classmethod
    def count(cls, text: str) -> int:
        """Count the number of tokens in a string."""
        if not text:
            return 0

        enc = cls._get_encoding()
        if enc is not None:
            try:
                return len(enc.encode(text, disallowed_special=()))
            except Exception:
                pass

        # Fallback estimation: average 1 token ~= 0.75 words or 4 characters in English
        words = len(text.split())
        return max(1, math.ceil(words * 1.33))

    @classmethod
    def truncate(cls, text: str, max_tokens: int) -> str:
        """Truncate text to fit within max_tokens."""
        if not text or max_tokens <= 0:
            return ""

        enc = cls._get_encoding()
        if enc is not None:
            try:
                tokens = enc.encode(text, disallowed_special=())
                if len(tokens) <= max_tokens:
                    return text
                return enc.decode(tokens[:max_tokens])
            except Exception:
                pass

        # Fallback word-based truncation
        words = text.split()
        estimated_max_words = int(max_tokens * 0.75)
        return " ".join(words[:estimated_max_words])

    @classmethod
    def split_by_tokens(cls, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Split a long string into token windows with overlap."""
        if not text:
            return []

        enc = cls._get_encoding()
        if enc is not None:
            try:
                tokens = enc.encode(text, disallowed_special=())
                if len(tokens) <= chunk_size:
                    return [text]

                chunks = []
                step = max(1, chunk_size - overlap)
                for i in range(0, len(tokens), step):
                    window = tokens[i : i + chunk_size]
                    chunks.append(enc.decode(window))
                    if i + chunk_size >= len(tokens):
                        break
                return chunks
            except Exception:
                pass

        # Fallback word-based windowing
        words = text.split()
        target_words = max(1, int(chunk_size * 0.75))
        overlap_words = max(0, int(overlap * 0.75))
        step_words = max(1, target_words - overlap_words)

        chunks = []
        for i in range(0, len(words), step_words):
            window = words[i : i + target_words]
            chunks.append(" ".join(window))
            if i + target_words >= len(words):
                break
        return chunks
