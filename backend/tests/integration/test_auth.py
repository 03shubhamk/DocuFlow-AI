"""
Integration tests for Authentication API endpoints (/api/v1/auth/*).

Tests:
- User registration & duplicate handling
- Login with valid & invalid credentials
- Token rotation with refresh token
- Token revocation on logout
- Current user /me endpoint
- Security attack vectors (expired tokens, invalid signatures, malformed payloads)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings


class TestAuthRegistration:
    def test_register_new_user_success(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "StrongPassword123!",
                "full_name": "New User",
                "tenant_name": "New Corp",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["role"] == "USER"
        assert data["is_active"] is True
        assert "id" in data
        assert "tenant_id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email_returns_409(self, client: TestClient):
        payload = {
            "email": "duplicate@example.com",
            "password": "StrongPassword123!",
            "full_name": "First User",
        }
        r1 = client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 201

        # Attempt to register with same email
        r2 = client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"].lower()

    def test_register_short_password_returns_422(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "shortpwd@example.com",
                "password": "short",
                "full_name": "Short Password",
            },
        )
        assert response.status_code == 422


class TestAuthLogin:
    def test_login_success_returns_token_pair(self, client: TestClient):
        # Register user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "loginuser@example.com",
                "password": "LoginPassword123!",
                "full_name": "Login User",
            },
        )

        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "LoginPassword123!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_login_wrong_password_returns_401(self, client: TestClient):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpwd@example.com",
                "password": "CorrectPassword123!",
                "full_name": "Wrong Pwd User",
            },
        )

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpwd@example.com",
                "password": "WrongPassword!",
            },
        )
        assert response.status_code == 401
        assert "invalid email address or password" in response.json()["detail"].lower()

    def test_login_nonexistent_email_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "ghost@example.com",
                "password": "SomePassword123!",
            },
        )
        assert response.status_code == 401


class TestAuthRefreshToken:
    def test_refresh_token_rotation_success(self, client: TestClient):
        # Register & login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "rotater@example.com",
                "password": "RotatePassword123!",
                "full_name": "Rotate User",
            },
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "rotater@example.com", "password": "RotatePassword123!"},
        )
        old_refresh = login_res.json()["refresh_token"]

        # Refresh
        refresh_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert refresh_res.status_code == 200
        new_data = refresh_res.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        new_refresh = new_data["refresh_token"]
        assert new_refresh != old_refresh

        # Using old refresh token again must fail (token rotation enforcement)
        replay_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert replay_res.status_code == 401

    def test_refresh_with_invalid_token_returns_401(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_fake_refresh_token_string_here"},
        )
        assert response.status_code == 401


class TestAuthProfileAndLogout:
    def test_get_me_authenticated(self, client: TestClient):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@example.com",
                "password": "MyPassword123!",
                "full_name": "Self User",
            },
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "me@example.com", "password": "MyPassword123!"},
        )
        token = login_res.json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["full_name"] == "Self User"

    def test_get_me_unauthenticated_returns_401(self, client: TestClient):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_logout_revokes_refresh_token(self, client: TestClient):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@example.com",
                "password": "LogoutPassword123!",
                "full_name": "Logout User",
            },
        )
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "logout@example.com", "password": "LogoutPassword123!"},
        )
        access_token = login_res.json()["access_token"]
        refresh_token = login_res.json()["refresh_token"]

        # Logout
        logout_res = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_res.status_code == 200
        assert "logged out" in logout_res.json()["detail"].lower()

        # Refresh must now fail
        refresh_res = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_res.status_code == 401


class TestSecurityAttackVectors:
    def test_expired_jwt_access_token_returns_401(self, client: TestClient):
        settings = get_settings()
        import uuid
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        past = datetime.now(timezone.utc) - timedelta(hours=2)
        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "role": "USER",
            "email": "hacker@test.com",
            "exp": past,
            "iat": past - timedelta(minutes=15),
            "type": "access",
        }
        expired_jwt = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_jwt}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_tampered_jwt_signature_returns_401(self, client: TestClient):
        import uuid
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "role": "ADMIN",
            "email": "spoof@test.com",
            "exp": now + timedelta(minutes=15),
            "iat": now,
            "type": "access",
        }
        # Signed with wrong secret
        fake_jwt = jwt.encode(
            payload, "wrong-secret-key-that-does-not-match-docuflow", algorithm="HS256"
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {fake_jwt}"},
        )
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, client: TestClient):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401

    def test_malformed_json_payload_returns_422(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            content="not-json-content",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
