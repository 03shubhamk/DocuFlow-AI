"""
Unit tests for security mechanisms (bcrypt hashing, JWT tokens, document access control).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import get_settings
from app.domain.entities import Document, User, UserRole
from app.domain.exceptions import InvalidTokenException, TokenExpiredException
from app.infrastructure.security.tokens import (
    create_access_token,
    create_token_pair,
    decode_access_token,
    generate_secure_random_token,
    hash_password,
    hash_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify_success(self):
        plain = "SuperSecurePassword123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_fails(self):
        plain = "SuperSecurePassword123!"
        hashed = hash_password(plain)
        assert verify_password("WrongPassword123!", hashed) is False

    def test_hashes_are_unique_with_salt(self):
        plain = "SamePassword123!"
        hash1 = hash_password(plain)
        hash2 = hash_password(plain)
        assert hash1 != hash2
        assert verify_password(plain, hash1) is True
        assert verify_password(plain, hash2) is True


class TestJWTTokens:
    def test_create_and_decode_token_success(self):
        settings = get_settings()
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        role = UserRole.USER.value
        email = "test@example.com"

        token, expires_at = create_access_token(
            settings=settings,
            subject=user_id,
            tenant_id=tenant_id,
            role=role,
            email=email,
        )

        assert isinstance(token, str)
        assert len(token) > 20
        assert expires_at > datetime.now(timezone.utc)

        payload = decode_access_token(settings, token)
        assert payload["sub"] == user_id
        assert payload["tenant_id"] == tenant_id
        assert payload["role"] == role
        assert payload["email"] == email
        assert payload["type"] == "access"

    def test_expired_token_raises_token_expired(self):
        settings = get_settings()
        now = datetime.now(timezone.utc) - timedelta(minutes=30)
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "role": "USER",
            "email": "expired@example.com",
            "exp": now,
            "iat": now - timedelta(minutes=15),
            "type": "access",
        }
        expired_token = jwt.encode(
            expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(TokenExpiredException):
            decode_access_token(settings, expired_token)

    def test_tampered_token_raises_invalid_token(self):
        settings = get_settings()
        token, _ = create_access_token(
            settings=settings,
            subject=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            role="USER",
            email="tamper@example.com",
        )
        tampered = token[:-4] + "fake"
        with pytest.raises(InvalidTokenException):
            decode_access_token(settings, tampered)

    def test_token_pair_creation(self):
        settings = get_settings()
        access_tok, refresh_tok, access_exp, refresh_exp = create_token_pair(
            settings=settings,
            user_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            role="USER",
            email="pair@example.com",
        )
        assert access_tok is not None
        assert refresh_tok is not None
        assert len(refresh_tok) > 40
        assert refresh_exp > access_exp

    def test_refresh_token_hashing(self):
        raw = generate_secure_random_token()
        h1 = hash_token(raw)
        h2 = hash_token(raw)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex string


class TestDocumentIsolation:
    def test_owner_can_access_own_document(self):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="u1@test.com",
            hashed_password="h",
            full_name="User One",
            role=UserRole.USER,
        )
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            owner_id=user_id,
            title="My Doc",
            original_filename="doc.pdf",
            file_type="application/pdf",
            file_size_bytes=1000,
            storage_path="path",
            checksum_sha256="c",
        )
        assert doc.is_accessible_by(user) is True

    def test_other_user_cannot_access_document(self):
        tenant_id = uuid.uuid4()
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()

        user2 = User(
            id=user2_id,
            tenant_id=tenant_id,
            email="u2@test.com",
            hashed_password="h",
            full_name="User Two",
            role=UserRole.USER,
        )
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            owner_id=user1_id,
            title="User1 Doc",
            original_filename="doc.pdf",
            file_type="application/pdf",
            file_size_bytes=1000,
            storage_path="path",
            checksum_sha256="c",
        )
        assert doc.is_accessible_by(user2) is False

    def test_admin_can_access_any_document_in_tenant(self):
        tenant_id = uuid.uuid4()
        user1_id = uuid.uuid4()
        admin_id = uuid.uuid4()

        admin = User(
            id=admin_id,
            tenant_id=tenant_id,
            email="admin@test.com",
            hashed_password="h",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            owner_id=user1_id,
            title="User1 Doc",
            original_filename="doc.pdf",
            file_type="application/pdf",
            file_size_bytes=1000,
            storage_path="path",
            checksum_sha256="c",
        )
        assert doc.is_accessible_by(admin) is True

    def test_user_cannot_access_document_from_different_tenant(self):
        tenant1_id = uuid.uuid4()
        tenant2_id = uuid.uuid4()
        user_id = uuid.uuid4()

        admin_tenant2 = User(
            id=user_id,
            tenant_id=tenant2_id,
            email="admin2@test.com",
            hashed_password="h",
            full_name="Admin T2",
            role=UserRole.ADMIN,
        )
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant1_id,
            owner_id=uuid.uuid4(),
            title="Tenant1 Doc",
            original_filename="doc.pdf",
            file_type="application/pdf",
            file_size_bytes=1000,
            storage_path="path",
            checksum_sha256="c",
        )
        assert doc.is_accessible_by(admin_tenant2) is False
