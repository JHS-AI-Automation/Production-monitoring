"""Observability-helpers: request-correlatie, logging-context en lichte in-process metrics.

Doel: een support-engineer kan een probleem terugvinden zonder de code te kennen.
- Elk request krijgt een request-id dat in de logs én in de X-Request-ID response-header staat.
- Een logging-filter zet dat request-id op elke log-record (text- en JSON-formaat).
- Een lichte in-memory metrics-teller (geen externe dependency) voedt /api/metrics.
"""

import logging
import time
from collections import defaultdict
from contextvars import ContextVar

# Correlatie-id voor het huidige request; "-" buiten request-context (bv. startup-logs).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Zet het huidige request-id op elke log-record, zodat formatters het kunnen tonen."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class Metrics:
    """Minimale in-process metrics. Genoeg voor 'hoe gaat het nu', zonder Prometheus.

    Cardinaliteit blijft laag: alleen API-paden worden los geteld, de rest valt onder 'static'.
    """

    def __init__(self) -> None:
        self.started = time.time()
        self.requests_total = 0
        self.errors_total = 0
        self._by_endpoint: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0}
        )

    def record(self, endpoint: str, status: int, duration_ms: float) -> None:
        self.requests_total += 1
        ep = self._by_endpoint[endpoint]
        ep["count"] += 1
        ep["total_ms"] += duration_ms
        ep["max_ms"] = max(ep["max_ms"], duration_ms)
        if status >= 500:
            self.errors_total += 1
            ep["errors"] += 1

    def snapshot(self) -> dict:
        endpoints = {
            name: {
                "count": v["count"],
                "errors": v["errors"],
                "avg_ms": round(v["total_ms"] / v["count"], 1) if v["count"] else 0,
                "max_ms": round(v["max_ms"], 1),
            }
            for name, v in sorted(self._by_endpoint.items())
        }
        return {
            "uptime_seconds": round(time.time() - self.started),
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "endpoints": endpoints,
        }


# Eén gedeelde instance voor het hele proces.
metrics = Metrics()
