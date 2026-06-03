"""API-tests via TestClient: observability-endpoints + (indien DB) de datapagina's."""


def test_version(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Optimax"
    assert {"version", "commit", "started_at"} <= body.keys()


def test_metrics_json(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "requests_total" in body
    assert "endpoints" in body


def test_metrics_prometheus(client):
    r = client.get("/api/metrics/prometheus")
    assert r.status_code == 200
    assert "optimax_requests_total" in r.text


def test_request_id_header_is_generated(client):
    r = client.get("/api/version")
    assert r.headers.get("x-request-id")


def test_request_id_header_is_propagated(client):
    r = client.get("/api/version", headers={"X-Request-ID": "test-rid-123"})
    assert r.headers.get("x-request-id") == "test-rid-123"


def test_client_log_accepts_post(client):
    r = client.post("/api/client-log", json={"message": "boom", "url": "/x", "stack": "..."})
    assert r.status_code == 204


def test_health_shape(client):
    r = client.get("/api/health")
    assert r.status_code in (200, 503)
    body = r.json()
    assert {"status", "version", "db_pool"} <= body.keys()


def test_future_date_is_rejected(client):
    # Validatie gebeurt vóór de DB, dus dit werkt ook zonder database.
    r = client.get("/api/alarms/stats?date=2099-01-01")
    assert r.status_code == 400


# --- DB-afhankelijk (overslaan als nep-DB niet draait) ---

def test_alarms_stats(client, require_db):
    r = client.get("/api/alarms/stats?date=2026-06-01")
    assert r.status_code == 200
    assert {"date", "resolved", "triggered"} <= r.json().keys()


def test_production_summary(client, require_db):
    r = client.get("/api/production/summary?date=2026-06-01")
    assert r.status_code == 200
    assert "per_line" in r.json()


def test_pallets_summary(client, require_db):
    r = client.get("/api/pallets/summary?date=2026-06-01")
    assert r.status_code == 200
    assert "stations" in r.json()


def test_alarms_list_pagination(client, require_db):
    r = client.get("/api/alarms/list?date=2026-06-01&page=1")
    assert r.status_code == 200
    body = r.json()
    assert {"items", "total", "pages"} <= body.keys()
