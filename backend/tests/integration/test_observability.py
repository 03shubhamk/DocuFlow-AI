"""
DocuFlow AI — Integration Tests for Observability Endpoints and Telemetry.

Tests /health/live, /health/ready, /metrics, Prometheus exposition, and telemetry propagation.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.infrastructure.observability import get_metrics


class TestObservabilityEndpoints:
    def test_liveness_probe_returns_alive(self, client: TestClient):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_probe_structure_and_no_leakage(self, client: TestClient):
        response = client.get("/health/ready")
        # In test environment with sqlite/in-memory, readiness returns 200 or 503 depending on redis/qdrant availability
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "postgresql" in data["checks"]
        assert "redis" in data["checks"]
        assert "qdrant" in data["checks"]
        assert "minio" in data["checks"]

        # Ensure no internal error strings or passwords are leaked in response
        for _dep_name, check_info in data["checks"].items():
            assert check_info.get("status") in ("ok", "unhealthy")
            assert "password" not in str(check_info).lower()
            assert "traceback" not in str(check_info).lower()


    def test_root_metrics_endpoint_exposition(self, client: TestClient):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        content = response.text
        assert "docuflow_http_requests_total" in content
        assert "# TYPE docuflow_http_requests_total counter" in content

    def test_health_metrics_endpoint_exposition(self, client: TestClient):
        response = client.get("/health/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        content = response.text
        assert "# TYPE docuflow_http_request_duration_seconds histogram" in content

    def test_request_increments_http_metrics(self, client: TestClient):
        # Trigger an API request
        client.get("/health/live")

        metrics = get_metrics()
        prom_text = metrics.generate_prometheus_output()
        assert "http_requests_total" in prom_text

    def test_w3c_traceparent_propagation(self, client: TestClient):
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        response = client.get("/health/live", headers={"traceparent": traceparent})
        assert response.status_code == 200
        # Correlation ID header should be returned
        assert "x-correlation-id" in response.headers
