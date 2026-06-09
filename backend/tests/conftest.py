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

# Repo-root op het pad zodat 'backend' importeerbaar is, ongeacht waar pytest draait.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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
