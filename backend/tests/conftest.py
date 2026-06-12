"""Test-fixtures voor de Optimax-verificatiesuite.

De API-tests draaien via FastAPI's TestClient (start de lifespan, dus de DB-pool).
DB-afhankelijke tests verwachten de nep-DB (zie README); zijn die niet bereikbaar,
dan worden ze netjes overgeslagen i.p.v. te falen.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# De testsuite draait in een afgeschermde context: sta expliciet toe dat de app
# zonder dashboard-authenticatie start (anders weigert lifespan te starten). MOET
# vóór de import van backend.main, want de vlag wordt bij import gelezen.
os.environ.setdefault("ALLOW_NO_AUTH", "1")
# Maintenance-endpoints zijn flag-gated (trunk-based); in tests altijd aan zodat de
# maintenance-suite meedraait en de CI no-skip-gate niet afgaat.
os.environ.setdefault("MAINTENANCE_ENABLED", "1")
# API-microcache default UIT in tests: gecachte antwoorden zouden anders tussen tests
# lekken (zelfde URL, andere gemockte data). De cache-tests zetten hem zelf gericht aan.
os.environ.setdefault("API_CACHE_TTL_SECONDS", "0")

# Repo-root op het pad zodat 'backend' importeerbaar is, ongeacht waar pytest draait.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# De SPA-routes registreren alleen als static/ bestaat (zie backend.main). In CI is de
# frontend niet gebouwd; maak een minimale stub zodat de cache-header-tests overal
# draaien i.p.v. stilletjes te skippen. MOET vóór de import van backend.main.
_static = Path(__file__).resolve().parents[2] / "static"
if not (_static / "index.html").exists():
    (_static / "assets").mkdir(parents=True, exist_ok=True)
    (_static / "index.html").write_text("<!doctype html><title>stub</title>", encoding="utf-8")

from backend.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def require_db(client):
    """Sla over als de database niet bereikbaar is."""
    resp = client.get("/api/health")
    if resp.status_code != 200 or resp.json().get("database") is not True:
        pytest.skip("Nep-DB niet bereikbaar; DB-afhankelijke test overgeslagen")
