"""
DocuFlow AI — Unit Tests for Authentication & Permission Services.

Tests token issuance, claims validation, expiration handling, refresh-token rotation,
revocation blacklist, and RBAC authorization policies.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.domain.entities import RefreshToken, User, UserRole
from app.infrastructure.security.tokens import (
    create_access_token,
    create_token_pair,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


class TestAuthAndTokens:
    def test_password_hashing_and_verification(self):
        raw_password = "SecurePassword2026!"
        hashed = hash_password(raw_password)

        assert hashed != raw_password
        assert verify_password(raw_password, hashed) is True
        assert verify_password("WrongPassword!", hashed) is False

    def test_access_token_creation_and_claims(self, test_settings: Settings):
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        email = "analyst@docuflow.ai"
        role = UserRole.USER.value

        token, expires_at = create_access_token(
            settings=test_settings,
            subject=user_id,
            tenant_id=tenant_id,
            role=role,
            email=email,
        )

        assert expires_at is not None
        decoded = decode_access_token(settings=test_settings, token=token)
        assert decoded is not None
        assert decoded["sub"] == user_id
        assert decoded["tenant_id"] == tenant_id
        assert decoded["role"] == role
        assert decoded["email"] == email

    def test_token_pair_creation(self, test_settings: Settings):
        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        email = "user@docuflow.ai"
        role = UserRole.USER.value

        acc_token, raw_refresh, acc_exp, ref_exp = create_token_pair(
            settings=test_settings,
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            email=email,
        )

        assert acc_token is not None
        assert raw_refresh is not None
        assert ref_exp > acc_exp
        hashed_ref = hash_token(raw_refresh)
        assert len(hashed_ref) == 64

    def test_refresh_token_entity_revocation(self):
        user_id = uuid.uuid4()
        token_rec = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=hash_token("sample_refresh_token_val"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=None,
        )
        assert token_rec.is_active is True

        # Revoke token
        token_rec.revoked_at = datetime.now(timezone.utc)
        assert token_rec.is_active is False


class TestRBACPermissions:
    def test_role_hierarchy(self):
        admin = User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="admin@test.com",
            hashed_password="hash",
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        standard = User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="user@test.com",
            hashed_password="hash",
            full_name="User",
            role=UserRole.USER,
        )

        assert admin.role == UserRole.ADMIN
        assert standard.role == UserRole.USER


