"""Tests voor de optionele HTTP Basic Auth (env-gated)."""

import base64

import pytest

import backend.main as main


@pytest.fixture
def auth_on(monkeypatch):
    """Zet auth tijdelijk aan (revert automatisch na de test)."""
    monkeypatch.setattr(main, "AUTH_USER", "u")
    monkeypatch.setattr(main, "AUTH_PASSWORD", "p")
    monkeypatch.setattr(main, "_AUTH_ENABLED", True)


def test_auth_disabled_allows_access(client):
    # Default: geen credentials gezet -> open (huidig gedrag).
    assert client.get("/api/version").status_code == 200


def test_auth_enabled_rejects_without_credentials(client, auth_on):
    assert client.get("/api/version").status_code == 401


def test_auth_enabled_allows_with_credentials(client, auth_on):
    token = base64.b64encode(b"u:p").decode()
    r = client.get("/api/version", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 200


def test_auth_enabled_rejects_wrong_credentials(client, auth_on):
    token = base64.b64encode(b"u:wrong").decode()
    r = client.get("/api/version", headers={"Authorization": f"Basic {token}"})
    assert r.status_code == 401


def test_health_stays_exempt_from_auth(client, auth_on):
    # /api/health moet vrij blijven voor de container-healthcheck.
    assert client.get("/api/health").status_code in (200, 503)
