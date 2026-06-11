"""Vaste regressietests voor de security-fixes uit de review van 2026-06-09.

Port van verify_security_fixes.py (security-review-sessie): die checks draaiden
eenmalig; hier draaien ze in elke CI-run mee. Dekt SEC-01/04/07/18/27/28 plus
de latere SEC-10 (lockout, zie ook test_units).
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- SEC-01: zonder auth en zonder ALLOW_NO_AUTH weigert de app te starten ---

def _start_app_subprocess(extra_env: dict) -> subprocess.CompletedProcess:
    code = (
        "import sys\n"
        f"sys.path.insert(0, r'{REPO_ROOT}')\n"
        "from fastapi.testclient import TestClient\n"
        "from backend.main import app\n"
        "with TestClient(app):\n"
        "    pass\n"
        "print('STARTED_OK')\n"
    )
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("DASHBOARD_AUTH_USER", "DASHBOARD_AUTH_PASSWORD", "ALLOW_NO_AUTH")
    }
    env.update({"DB_HOST": "127.0.0.1", "DB_NAME": "x", "DB_USER": "x", "DB_PASSWORD": "x"})
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120
    )


def test_sec01_start_geweigerd_zonder_auth():
    res = _start_app_subprocess({})
    assert res.returncode != 0, "app hoort te weigeren zonder dashboard-auth"
    assert "Start geweigerd" in (res.stdout + res.stderr)


def test_sec01_interne_modus_start_wel():
    res = _start_app_subprocess({"ALLOW_NO_AUTH": "1"})
    assert res.returncode == 0, res.stderr
    assert "STARTED_OK" in res.stdout


# --- SEC-27/28: metrics-cardinaliteit begrensd + geen rauwe paden in prometheus ---

def test_sec27_metrics_cardinaliteit_begrensd(client):
    for i in range(5):
        client.get(f"/api/zzrandom{i}")
    eps = client.get("/api/metrics").json()["endpoints"]
    assert not [k for k in eps if k.startswith("/api/zzrandom")], "rauw pad lekte naar metrics"
    assert "api_other" in eps


def test_sec28_prometheus_geen_rauwe_paden(client):
    client.get("/api/zzrandom-prom")
    r = client.get("/api/metrics/prometheus")
    assert r.status_code == 200
    assert "zzrandom" not in r.text


# --- SEC-07: client-log body-cap ---

def test_sec07_grote_clientlog_body_413(client):
    r = client.post("/api/client-log", content=b"x" * 20000)
    assert r.status_code == 413


# --- SEC-18: dagbudget bereikt -> 503 met klantvriendelijke melding ---

def test_sec18_dagbudget_503(monkeypatch):
    from backend.routers import chat

    monkeypatch.setattr(chat, "_daily_token_budget", 100)
    monkeypatch.setattr(chat, "_tokens_today", 200)
    monkeypatch.setattr(chat, "_token_day", time.strftime("%Y-%m-%d", time.gmtime()))
    with pytest.raises(HTTPException) as exc:
        chat._check_token_budget()
    assert exc.value.status_code == 503
    assert "limiet" in exc.value.detail  # klantvriendelijke tekst, geen env-var-jargon


# --- SEC-04: chat schakelt uit zonder read-only rol in productie ---

def _chat_settings(chat_user: str):
    from backend.config import Settings

    return Settings(
        db_host="127.0.0.1", db_port=5432, db_name="x", db_user="x", db_password="x",
        app_port=8080, app_host="127.0.0.1", openrouter_api_key="sk-test",
        chat_model="test-model", chat_db_user=chat_user, chat_db_password="",
        chat_tls_verify=True, chat_ca_bundle="", chat_daily_token_budget=1000,
    )


def test_sec04_chat_uit_zonder_readonly_rol_in_prod(monkeypatch):
    from backend.routers import chat

    monkeypatch.setattr(chat, "_client", None)
    monkeypatch.setattr(chat, "_chat_pool", None)

    # Productie-modus (geen ALLOW_NO_AUTH): chat hoort UIT te staan, nooit
    # stilletjes terugvallen op de (mogelijk schrijf-bevoegde) hoofd-pool.
    monkeypatch.delenv("ALLOW_NO_AUTH", raising=False)
    asyncio.run(chat.init_chat(_chat_settings("")))
    assert chat._client is None

    # Interne modus: fallback is expliciet toegestaan, chat mag aan.
    monkeypatch.setenv("ALLOW_NO_AUTH", "1")
    asyncio.run(chat.init_chat(_chat_settings("")))
    assert chat._client is not None


# --- SEC-10: brute-force-lockout end-to-end via de API ---

def test_sec10_lockout_via_api(client, monkeypatch):
    from backend import main

    monkeypatch.setattr(main, "_AUTH_ENABLED", True)
    monkeypatch.setattr(main, "AUTH_USER", "testuser")
    monkeypatch.setattr(main, "AUTH_PASSWORD", "testpass")
    monkeypatch.setattr(main, "_auth_failures", {})

    for _ in range(main._AUTH_MAX_FAILURES):
        assert client.get("/api/version").status_code == 401
    r = client.get("/api/version")
    assert r.status_code == 429
    assert r.headers.get("retry-after")
    # /api/health blijft vrij voor de container-healthcheck, ook tijdens lockout.
    assert client.get("/api/health").status_code in (200, 503)
