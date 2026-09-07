"""
Integration tests for health endpoints.

Uses FastAPI TestClient to verify the liveness endpoint returns 200.
"""

from __future__ import annotations


class TestHealthEndpoints:
    def test_liveness_returns_200(self, client):
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_build_info_returns_200(self, client):
        response = client.get("/health/info")
        assert response.status_code == 200
        data = response.json()
        assert data["api_version"] == "v1"
        assert "DocuFlow" in data["project"]
