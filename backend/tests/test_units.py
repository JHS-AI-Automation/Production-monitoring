"""Unit-tests: pure logica, geen DB of server nodig."""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from backend.observability import Metrics
from backend.routers.alarms import escape_like
from backend.routers.chat import _sanitize_sql
from backend.timewindow import MAX_TREND_DAYS, factory_today, validate_date, validate_range


# --- alarmlijst zoekterm-escape ---

def test_escape_like_neutralizes_wildcards():
    assert escape_like("100%_klaar") == "100\\%\\_klaar"
    assert escape_like("pad\\naam") == "pad\\\\naam"
    assert escape_like("gewone tekst") == "gewone tekst"


# --- timewindow ---
# Verwachtingen rekenen met factory_today() (Amsterdam), net als de implementatie:
# op een host in een andere tijdzone zou date.today() rond middernacht afwijken.

def test_validate_date_default_is_yesterday():
    assert validate_date(None) == factory_today() - timedelta(days=1)


def test_validate_date_rejects_future():
    with pytest.raises(HTTPException):
        validate_date(factory_today() + timedelta(days=1))


def test_validate_date_accepts_past():
    d = factory_today() - timedelta(days=5)
    assert validate_date(d) == d


def test_validate_range_defaults_to_last_30_days():
    frm, to = validate_range(None, None)
    assert to == factory_today() - timedelta(days=1)
    assert (to - frm).days == 29


def test_validate_range_rejects_from_after_to():
    with pytest.raises(HTTPException):
        validate_range(date(2026, 1, 2), date(2026, 1, 1))


def test_validate_range_caps_period():
    with pytest.raises(HTTPException):
        validate_range(
            factory_today() - timedelta(days=MAX_TREND_DAYS + 5),
            factory_today() - timedelta(days=1),
        )


# --- chat SQL-sanitizer (defense-in-depth) ---

def test_sanitize_sql_allows_select_and_enforces_outer_limit():
    out = _sanitize_sql("SELECT 1")
    assert out.upper().startswith("SELECT * FROM (")
    assert out.endswith("LIMIT 1000")


def test_sanitize_sql_outer_limit_caps_inner_limit():
    # Een binnen-LIMIT van het model (hoe groot ook) wordt door de wrap op
    # MAX_ROWS gemaximeerd; de binnen-LIMIT blijft gewoon staan.
    out = _sanitize_sql("SELECT * FROM plc_alarms LIMIT 999999")
    assert "LIMIT 999999" in out
    assert out.endswith("LIMIT 1000")


def test_sanitize_sql_allows_cte():
    out = _sanitize_sql("WITH x AS (SELECT 1 AS n) SELECT n FROM x")
    assert "WITH x AS" in out
    assert out.endswith("LIMIT 1000")


def test_sanitize_sql_rejects_non_select():
    with pytest.raises(ValueError):
        _sanitize_sql("UPDATE plc_alarms SET x = 1")


def test_sanitize_sql_rejects_forbidden_keyword():
    with pytest.raises(ValueError):
        _sanitize_sql("SELECT 1; DROP TABLE plc_alarms")


def test_sanitize_sql_rejects_multi_statement():
    # Ook zonder verboden keyword zijn meerdere statements niet toegestaan.
    with pytest.raises(ValueError):
        _sanitize_sql("SELECT 1; SELECT 2")


def test_sanitize_sql_rejects_select_into_and_set():
    # SELECT ... INTO maakt een tabel aan (verkapte CREATE); SET wijzigt de sessie.
    with pytest.raises(ValueError):
        _sanitize_sql("SELECT * INTO evil_copy FROM plc_alarms")
    with pytest.raises(ValueError):
        _sanitize_sql("SET search_path TO public")


# --- productie: verwachte shift-minuten (voor datagat-rapportage) ---

def test_expected_shift_minutes_full_past_day():
    from datetime import datetime
    from backend.routers.production import SHIFT_MINUTES, expected_shift_minutes
    from backend.timewindow import FACTORY_TZ
    now = datetime(2026, 6, 11, 12, 0, tzinfo=FACTORY_TZ)
    assert expected_shift_minutes(date(2026, 6, 10), now=now) == SHIFT_MINUTES


def test_expected_shift_minutes_today_partial():
    from datetime import datetime
    from backend.routers.production import expected_shift_minutes
    from backend.timewindow import FACTORY_TZ
    # Om 07:00 zijn er 2 uur shift (05:00-07:00) verstreken -> 120 minuten verwacht.
    now = datetime(2026, 6, 11, 7, 0, tzinfo=FACTORY_TZ)
    assert expected_shift_minutes(date(2026, 6, 11), now=now) == 120
    # Voor de shift-start: nog niets verwacht.
    early = datetime(2026, 6, 11, 4, 0, tzinfo=FACTORY_TZ)
    assert expected_shift_minutes(date(2026, 6, 11), now=early) == 0
    # Na shift-eind: de volle shift.
    late = datetime(2026, 6, 11, 23, 30, tzinfo=FACTORY_TZ)
    assert expected_shift_minutes(date(2026, 6, 11), now=late) == 1080


# --- Basic Auth brute-force-lockout (SEC-10) ---

def test_auth_lockout_after_max_failures(monkeypatch):
    from backend import main
    monkeypatch.setattr(main, "_auth_failures", {})
    for _ in range(main._AUTH_MAX_FAILURES):
        main._register_auth_failure("10.0.0.1")
    assert main._auth_locked("10.0.0.1")
    assert not main._auth_locked("10.0.0.2")  # ander IP blijft vrij


def test_auth_lockout_expires_after_window(monkeypatch):
    import time
    from backend import main
    expired = time.monotonic() - main._AUTH_WINDOW_SECONDS - 1
    monkeypatch.setattr(main, "_auth_failures", {"10.0.0.1": [expired] * 20})
    assert not main._auth_locked("10.0.0.1")
    # verlopen entries zijn opgeruimd (geen geheugenlek)
    assert "10.0.0.1" not in main._auth_failures


# --- database lazy reconnect (stroomuitval-scenario) ---

def test_db_lazy_reconnect_restores_pool(monkeypatch):
    """Pool weg + DB weer bereikbaar -> get_connection herstelt de pool vanzelf."""
    import asyncio
    from types import SimpleNamespace
    from backend import database

    fake_settings = SimpleNamespace(db_host="test-db", db_port=5432, db_name="test")

    class FakeAcquire:
        async def __aenter__(self):
            return "fake-conn"
        async def __aexit__(self, *exc):
            return False

    class FakePool:
        def acquire(self):
            return FakeAcquire()

    async def fake_create(settings, **kw):
        return FakePool()

    async def scenario():
        monkeypatch.setattr(database, "_pool", None)
        monkeypatch.setattr(database, "_settings", fake_settings)
        monkeypatch.setattr(database, "_last_attempt", float("-inf"))
        monkeypatch.setattr(database, "create_db_pool", fake_create)
        async with database.get_connection() as conn:
            assert conn == "fake-conn"
        assert database._pool is not None

    asyncio.run(scenario())


def test_db_reconnect_backoff_limits_attempts(monkeypatch):
    """Mislukte reconnect -> binnen het backoff-interval geen tweede poging."""
    import asyncio
    from types import SimpleNamespace
    from backend import database

    calls = []

    async def failing_create(settings, **kw):
        calls.append(1)
        raise OSError("db down")

    async def scenario():
        monkeypatch.setattr(database, "_pool", None)
        monkeypatch.setattr(
            database, "_settings", SimpleNamespace(db_host="test-db", db_port=5432, db_name="test")
        )
        monkeypatch.setattr(database, "_last_attempt", float("-inf"))
        monkeypatch.setattr(database, "create_db_pool", failing_create)

        with pytest.raises(RuntimeError):
            async with database.get_connection():
                pass
        with pytest.raises(RuntimeError):
            async with database.get_connection():
                pass
        # Eén echte poging; de tweede request valt binnen de backoff.
        assert len(calls) == 1

    asyncio.run(scenario())


# --- metrics ---

def test_metrics_records_and_aggregates():
    m = Metrics()
    m.record("/api/x", 200, 10)
    m.record("/api/x", 500, 30)
    snap = m.snapshot()
    assert snap["requests_total"] == 2
    assert snap["errors_total"] == 1
    ep = snap["endpoints"]["/api/x"]
    assert ep["count"] == 2
    assert ep["errors"] == 1
    assert ep["avg_ms"] == 20.0
    assert ep["max_ms"] == 30.0
