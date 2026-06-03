"""Unit-tests: pure logica, geen DB of server nodig."""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from backend.observability import Metrics
from backend.routers.chat import _sanitize_sql
from backend.timewindow import MAX_TREND_DAYS, validate_date, validate_range


# --- timewindow ---

def test_validate_date_default_is_yesterday():
    assert validate_date(None) == date.today() - timedelta(days=1)


def test_validate_date_rejects_future():
    with pytest.raises(HTTPException):
        validate_date(date.today() + timedelta(days=1))


def test_validate_date_accepts_past():
    d = date.today() - timedelta(days=5)
    assert validate_date(d) == d


def test_validate_range_defaults_to_last_30_days():
    frm, to = validate_range(None, None)
    assert to == date.today() - timedelta(days=1)
    assert (to - frm).days == 29


def test_validate_range_rejects_from_after_to():
    with pytest.raises(HTTPException):
        validate_range(date(2026, 1, 2), date(2026, 1, 1))


def test_validate_range_caps_period():
    with pytest.raises(HTTPException):
        validate_range(
            date.today() - timedelta(days=MAX_TREND_DAYS + 5),
            date.today() - timedelta(days=1),
        )


# --- chat SQL-sanitizer (defense-in-depth) ---

def test_sanitize_sql_allows_select_and_adds_limit():
    out = _sanitize_sql("SELECT 1")
    assert out.upper().startswith("SELECT")
    assert "LIMIT" in out.upper()


def test_sanitize_sql_keeps_existing_limit():
    out = _sanitize_sql("SELECT * FROM plc_alarms LIMIT 5")
    assert out.upper().count("LIMIT") == 1


def test_sanitize_sql_rejects_non_select():
    with pytest.raises(ValueError):
        _sanitize_sql("UPDATE plc_alarms SET x = 1")


def test_sanitize_sql_rejects_forbidden_keyword():
    with pytest.raises(ValueError):
        _sanitize_sql("SELECT 1; DROP TABLE plc_alarms")


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
