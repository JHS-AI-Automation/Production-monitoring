"""Tests voor de Maintenance-feature: slijtage-detectie + endpoints (synthetische data)."""

from backend.maintenance import data
from backend.maintenance.wear import MIN_DAYS, analyze_motor, detect_wear


def _history(peaks):
    return [{"date": f"2026-01-{i+1:02d}", "start_a": 0.05, "peak_a": p} for i, p in enumerate(peaks)]


# --- detectie-logica (pure functie) ---

def test_stable_motor_is_ok():
    a = analyze_motor(_history([3.0] * 40))
    assert a is not None
    assert a["status"] == "ok"
    assert abs(a["increase_pct"]) < 1


def test_drifting_motor_raises_alarm():
    # van 3.0 langzaam naar 3.6 -> ruim boven de drempel
    peaks = [3.0 + 0.015 * i for i in range(40)]
    a = analyze_motor(_history(peaks))
    assert a["status"] == "alarm"
    assert a["increase_pct"] >= 15
    assert a["current_a"] > a["baseline_a"]
    assert a["since_days"] > 0


def test_mild_drift_is_warn_not_alarm():
    # ~10% stijging: boven warn (8%), onder alarm (15%)
    peaks = [3.0 + 0.008 * i for i in range(40)]
    a = analyze_motor(_history(peaks))
    assert a["status"] == "warn"


def test_too_little_data_returns_none():
    assert analyze_motor(_history([3.0] * (MIN_DAYS - 1))) is None


def test_small_absolute_change_no_false_alarm():
    # Kleine waarden (0.5 A) die procentueel stijgen maar absoluut < MIN_ABS_A blijven 'ok'.
    peaks = [0.50 + 0.001 * i for i in range(40)]
    a = analyze_motor(_history(peaks))
    assert a["status"] == "ok"


def test_detect_wear_flags_drifting_synthetic_motors():
    motors = data.get_motors()
    histories = data.get_all_histories(60)
    signals = detect_wear(motors, histories)
    flagged = {s["motor_id"] for s in signals}
    # Motor 8 (sterke drift) hoort er zeker bij; motor 1 (stabiel) zeker niet.
    assert 8 in flagged
    assert 1 not in flagged
    # Alarm staat vooraan in de lijst.
    if signals:
        assert signals[0]["status"] in ("alarm", "warn")
        assert "Controleer" in signals[0]["advice"]


# --- endpoints ---

def test_motors_endpoint_shape(client):
    r = client.get("/api/maintenance/motors")
    assert r.status_code == 200
    body = r.json()
    assert len(body["motors"]) == 12
    assert {"id", "name", "line", "status"} <= body["motors"][0].keys()


def test_motor_history_endpoint(client):
    r = client.get("/api/maintenance/motors/8/history?days=60")
    assert r.status_code == 200
    body = r.json()
    assert body["motor_id"] == 8
    assert len(body["history"]) > 0
    assert {"date", "start_a", "peak_a"} <= body["history"][0].keys()


def test_unknown_motor_404(client):
    assert client.get("/api/maintenance/motors/999/history").status_code == 404


def test_days_bounds_rejected(client):
    # De ge/le-grenzen op de days-parameter zijn een bewuste resource-grens.
    assert client.get("/api/maintenance/motors?days=13").status_code == 422
    assert client.get("/api/maintenance/motors?days=181").status_code == 422


def test_signals_endpoint(client):
    r = client.get("/api/maintenance/signals")
    assert r.status_code == 200
    assert isinstance(r.json()["signals"], list)
