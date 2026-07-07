"""Тесты для reverse-proxy — проверка формирования upstream URL.

Проверяет что прокси обращается к URL'ам, указанным в settings.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from demo.web.server import app


@pytest.fixture
def client():
    with respx.mock:
        http_client = httpx.AsyncClient(timeout=30.0)
        app.state.http_client = http_client
        test_client = TestClient(app)
        yield test_client
        test_client.close()


class TestProxyUsesSettingsUrls:
    """Прокси обращается к URL'ам из settings."""

    @respx.mock
    def test_data_service_proxy_hits_settings_url(self, client):
        """Прокси data-service бьёт именно в settings.data_service_url."""
        from demo.settings import settings

        expected_base = settings.data_service_url
        upstream_route = respx.get(f"{expected_base}/students").mock(
            return_value=httpx.Response(200, json=[{"id": "1"}])
        )
        response = client.get("/api/data/students")
        assert response.status_code == 200

        # httpx.URL — сравниваем как строку
        actual_url = str(upstream_route.calls.last.request.url)
        assert actual_url.startswith(expected_base), (
            f"Expected request to start with {expected_base}, got {actual_url}"
        )

    @respx.mock
    def test_rag_service_proxy_hits_settings_url(self, client):
        """Прокси rag бьёт именно в settings.rag_service_url."""
        from demo.settings import settings

        expected_base = settings.rag_service_url
        upstream_route = respx.post(f"{expected_base}/documents/list").mock(
            return_value=httpx.Response(200, json={"documents": []})
        )
        response = client.get("/api/rag/documents")
        assert response.status_code == 200
        actual_url = str(upstream_route.calls.last.request.url)
        assert actual_url.startswith(expected_base)

    @respx.mock
    def test_tenant_proxy_data_hits_settings_url(self, client):
        """Tenant-прокси для data бьёт в settings.data_service_url."""
        from demo.settings import settings

        expected_base = settings.data_service_url
        upstream_route = respx.get(f"{expected_base}/students").mock(
            return_value=httpx.Response(200, json=[])
        )
        response = client.get("/api/tenant/tenant-a/data/students")
        assert response.status_code == 200
        actual_url = str(upstream_route.calls.last.request.url)
        assert actual_url.startswith(expected_base)

    @respx.mock
    def test_tenant_proxy_rag_hits_settings_url(self, client):
        """Tenant-прокси для rag бьёт в settings.rag_service_url."""
        from demo.settings import settings

        expected_base = settings.rag_service_url
        upstream_route = respx.post(f"{expected_base}/documents/list").mock(
            return_value=httpx.Response(200, json={"documents": []})
        )
        response = client.get("/api/tenant/tenant-b/rag/documents")
        assert response.status_code == 200
        actual_url = str(upstream_route.calls.last.request.url)
        assert actual_url.startswith(expected_base)
