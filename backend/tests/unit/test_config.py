"""Unit tests for configuration validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestSettings:
    def test_settings_load_from_env(self, monkeypatch):
        """Settings should load all required vars from environment."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host:5432/db")
        monkeypatch.setenv("DATABASE_SYNC_URL", "postgresql://u:p@host:5432/db")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)

        # Clear lru_cache
        from app.config import Settings

        s = Settings()
        assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"
        assert s.is_development is True

    def test_jwt_secret_too_short_raises(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host:5432/db")
        monkeypatch.setenv("DATABASE_SYNC_URL", "postgresql://u:p@host:5432/db")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("JWT_SECRET_KEY", "short")

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_environment_raises(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "invalid_env")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host:5432/db")
        monkeypatch.setenv("DATABASE_SYNC_URL", "postgresql://u:p@host:5432/db")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings()
