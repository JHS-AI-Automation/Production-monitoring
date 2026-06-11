import base64
import logging
import os
import secrets
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.database import check_health, close_pool, init_pool, pool_stats
from backend.observability import RequestIdFilter, metrics, request_id_ctx
from backend.routers.alarms import router as alarms_router
from backend.routers.chat import router as chat_router, init_chat, close_chat_pool
from backend.routers.pallets import router as pallets_router
from backend.routers.production import router as production_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

# Versie-info voor support: "welke build draait er". APP_COMMIT kan via de build
# worden meegegeven (bv. docker build --build-arg / env in de container).
APP_VERSION = "1.1.0"
APP_COMMIT = os.environ.get("APP_COMMIT", "unknown")
STARTED_AT = datetime.now(timezone.utc)

# Optionele HTTP Basic Auth. Leeg = uit (open op het netwerk, huidig gedrag).
# Beide gezet = alle routes vereisen login, behalve /api/health (voor de container-healthcheck).
AUTH_USER = os.environ.get("DASHBOARD_AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("DASHBOARD_AUTH_PASSWORD", "")
_AUTH_ENABLED = bool(AUTH_USER and AUTH_PASSWORD)
_AUTH_EXEMPT = {"/api/health"}

# Veiligheid: zonder ingestelde authenticatie weigert de app te starten (productie-default).
# Voor een afgeschermde interne/test-omgeving kan dit expliciet worden uitgezet met ALLOW_NO_AUTH=1.
_ALLOW_NO_AUTH = os.environ.get("ALLOW_NO_AUTH", "").strip().lower() in ("1", "true", "yes")

# Bekende API-paden, gevuld bij startup. Metrics worden op dit lage-cardinaliteitslabel geteld
# i.p.v. op het rauwe request-pad: dat voorkomt onbegrensde geheugengroei en label-injectie
# via willekeurige /api/<x>-paden (die op de SPA-catch-all vallen).
_KNOWN_API_PATHS: set[str] = set()


def _metrics_label(path: str) -> str:
    """Lage-cardinaliteitslabel voor metrics: alleen bekende API-paden los, rest gebundeld."""
    if path in _KNOWN_API_PATHS:
        return path
    return "static" if not path.startswith("/api/") else "api_other"


# Security-response-headers (SEC-08). CSP: alles same-origin; 'unsafe-inline' voor styles
# is nodig voor de inline style-attributen van Recharts en het <style>-blok in het
# SVG-fabrieksschema. Geen externe bronnen: het dashboard draait air-gapped op de edge.
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


def _apply_response_headers(response, path: str) -> None:
    """Security-headers op elke response + cache-strategie voor de SPA:
    gehashte assets een jaar immutable, index.html (en de SPA-fallback) no-cache,
    zodat een nieuwe deploy direct zichtbaar is ondanks trage VPN/kiosk-caching."""
    response.headers.update(_SECURITY_HEADERS)
    if path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"


def _auth_ok(request: Request) -> bool:
    """Valideer HTTP Basic credentials in constante tijd."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
        user, _, pwd = decoded.partition(":")
    except Exception:
        return False
    return secrets.compare_digest(user, AUTH_USER) and secrets.compare_digest(pwd, AUTH_PASSWORD)


# Brute-force-lockout op Basic Auth (SEC-10): na _AUTH_MAX_FAILURES mislukte pogingen
# binnen het venster krijgt dat IP een 429 tot het venster is verlopen. Let op: net als
# bij de chat-rate-limit delen gebruikers achter hetzelfde kantoor-NAT één IP.
_AUTH_MAX_FAILURES = 10
_AUTH_WINDOW_SECONDS = 300
_auth_failures: dict[str, list[float]] = {}


def _auth_locked(ip: str) -> bool:
    """Is dit IP geblokkeerd? Ruimt en passant verlopen pogingen op (geen geheugenlek)."""
    now = time.monotonic()
    for known in list(_auth_failures):
        fresh = [t for t in _auth_failures[known] if now - t < _AUTH_WINDOW_SECONDS]
        if fresh:
            _auth_failures[known] = fresh
        else:
            del _auth_failures[known]
    return len(_auth_failures.get(ip, [])) >= _AUTH_MAX_FAILURES


def _register_auth_failure(ip: str) -> None:
    _auth_failures.setdefault(ip, []).append(time.monotonic())


def _setup_logging() -> None:
    import json
    from logging.handlers import RotatingFileHandler

    log_format = os.environ.get("LOG_FORMAT", "text")
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "request_id": getattr(record, "request_id", "-"),
                "message": record.getMessage(),
            }
            if record.exc_info and record.exc_info[1]:
                entry["error_type"] = type(record.exc_info[1]).__name__
                entry["traceback"] = traceback.format_exception(*record.exc_info)
            return json.dumps(entry, ensure_ascii=False, default=str)

    text_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.root.handlers.clear()
    logging.root.setLevel(level)
    request_id_filter = RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JSONFormatter() if log_format == "json" else text_formatter)
    console.addFilter(request_id_filter)
    logging.root.addHandler(console)

    # 5MB per bestand, 5 bestanden bewaard = max 25MB logs
    file_handler = RotatingFileHandler(
        log_dir / "dashboard.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(request_id_filter)
    logging.root.addHandler(file_handler)


_setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Productie-default: weiger te starten zonder dashboard-authenticatie.
    # ALLOW_NO_AUTH=1 is de bewuste escape voor een afgeschermde interne/test-omgeving.
    if not _AUTH_ENABLED and not _ALLOW_NO_AUTH:
        logger.critical(
            "Start geweigerd: geen dashboard-authenticatie ingesteld. Zet "
            "DASHBOARD_AUTH_USER en DASHBOARD_AUTH_PASSWORD in .env, of zet expliciet "
            "ALLOW_NO_AUTH=1 voor een afgeschermde interne omgeving."
        )
        raise SystemExit(1)

    # Vul de set bekende API-paden voor lage-cardinaliteit metrics-labels (zie _metrics_label).
    _KNOWN_API_PATHS.update(
        p for r in app.routes
        if (p := getattr(r, "path", "")).startswith("/api/") and "{" not in p
    )

    settings = Settings.from_env()
    await init_pool(settings)
    await init_chat(settings)
    logger.info("Optimax started on %s:%s", settings.app_host, settings.app_port)
    yield
    await close_chat_pool()
    await close_pool()


app = FastAPI(title="Optimax", lifespan=lifespan)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    # Hergebruik een binnenkomend X-Request-ID (bv. van een reverse proxy) of genereer er een.
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = request_id_ctx.set(request_id)
    start = time.monotonic()
    path = request.url.path
    try:
        # Optionele Basic Auth (env-gated). /api/health blijft vrij voor de healthcheck.
        if _AUTH_ENABLED and path not in _AUTH_EXEMPT:
            client_ip = request.client.host if request.client else "unknown"
            # Lockout (SEC-10) gaat vóór de credential-check: een gelockt IP krijgt
            # geen nieuwe pogingen, ook niet met de juiste credentials.
            if _auth_locked(client_ip):
                duration_ms = (time.monotonic() - start) * 1000
                metrics.record(_metrics_label(path), 429, duration_ms)
                logger.warning("Auth-lockout actief voor %s (%s %s)", client_ip, request.method, path)
                resp = JSONResponse(
                    {"detail": "Te veel mislukte inlogpogingen. Probeer het over enkele minuten opnieuw."},
                    status_code=429,
                    headers={"Retry-After": str(_AUTH_WINDOW_SECONDS), "X-Request-ID": request_id},
                )
                _apply_response_headers(resp, path)
                return resp
            if not _auth_ok(request):
                _register_auth_failure(client_ip)
                duration_ms = (time.monotonic() - start) * 1000
                # 401's tellen mee in de metrics zodat brute-force-pogingen zichtbaar zijn.
                metrics.record(_metrics_label(path), 401, duration_ms)
                logger.warning("Auth geweigerd: %s %s", request.method, path)
                resp = JSONResponse(
                    {"detail": "Niet geautoriseerd"},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Optimax"', "X-Request-ID": request_id},
                )
                _apply_response_headers(resp, path)
                return resp
            # Succesvolle login wist de mislukte pogingen van dit IP.
            _auth_failures.pop(client_ip, None)
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        metrics.record(_metrics_label(path), response.status_code, duration_ms)
        response.headers["X-Request-ID"] = request_id
        _apply_response_headers(response, path)
        if response.status_code >= 400:
            logger.warning(
                "%s %s -> %d (%dms)",
                request.method, path, response.status_code, round(duration_ms),
            )
        return response
    except Exception:
        duration_ms = (time.monotonic() - start) * 1000
        metrics.record(_metrics_label(path), 500, duration_ms)
        logger.exception(
            "Unhandled error: %s %s (%dms)", request.method, path, round(duration_ms),
        )
        resp = JSONResponse(
            {"detail": "Internal server error", "request_id": request_id}, status_code=500
        )
        resp.headers["X-Request-ID"] = request_id
        _apply_response_headers(resp, path)
        return resp
    finally:
        request_id_ctx.reset(token)


app.include_router(alarms_router)
app.include_router(production_router)
app.include_router(pallets_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    db_ok = await check_health()
    status = "healthy" if db_ok else "unhealthy"
    code = 200 if db_ok else 503
    return JSONResponse(
        {
            "status": status,
            "database": db_ok,
            "version": APP_VERSION,
            "uptime_seconds": round((datetime.now(timezone.utc) - STARTED_AT).total_seconds()),
            "db_pool": pool_stats(),
        },
        status_code=code,
    )


@app.get("/api/version")
async def version():
    """Welke build draait er, voor support en deploy-verificatie."""
    return {
        "name": "Optimax",
        "version": APP_VERSION,
        "commit": APP_COMMIT,
        "started_at": STARTED_AT.isoformat(),
    }


@app.get("/api/metrics")
async def metrics_endpoint():
    """Lichte in-process metrics: verzoeken, fouten en latency per endpoint."""
    snap = metrics.snapshot()
    snap["db_pool"] = pool_stats()
    return snap


@app.get("/api/metrics/prometheus")
async def metrics_prometheus():
    """Zelfde metrics in Prometheus text-exposition-formaat (scrape-baar, geen extra dependency)."""
    snap = metrics.snapshot()
    pool = pool_stats() or {}
    lines = [
        "# HELP optimax_uptime_seconds Process uptime",
        "# TYPE optimax_uptime_seconds gauge",
        f"optimax_uptime_seconds {snap['uptime_seconds']}",
        "# HELP optimax_requests_total Total HTTP requests",
        "# TYPE optimax_requests_total counter",
        f"optimax_requests_total {snap['requests_total']}",
        "# HELP optimax_errors_total Total 5xx responses",
        "# TYPE optimax_errors_total counter",
        f"optimax_errors_total {snap['errors_total']}",
        "# HELP optimax_endpoint_requests_total Requests per endpoint",
        "# TYPE optimax_endpoint_requests_total counter",
    ]
    for ep, v in snap["endpoints"].items():
        # Escape per Prometheus-exposition-spec (backslash, quote, newline) tegen label-injectie.
        label = ep.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "").replace("\r", "")
        lines.append(f'optimax_endpoint_requests_total{{endpoint="{label}"}} {v["count"]}')
        lines.append(f'optimax_endpoint_errors_total{{endpoint="{label}"}} {v["errors"]}')
        lines.append(f'optimax_endpoint_latency_ms_avg{{endpoint="{label}"}} {v["avg_ms"]}')
        lines.append(f'optimax_endpoint_latency_ms_max{{endpoint="{label}"}} {v["max_ms"]}')
    for key in ("size", "idle", "in_use", "max_size"):
        if key in pool:
            lines.append(f"optimax_db_pool_{key} {pool[key]}")
    return PlainTextResponse("\n".join(lines) + "\n")


# Harde bovengrens op de client-log-body: ruim voldoende voor een stacktrace, maar voorkomt
# dat een (ongeauthenticeerd) verzoek met een enorme payload het geheugen van het edge-device
# belast. 16 KB ~ 2000 tekens stack + marge.
_MAX_CLIENT_LOG_BYTES = 16_384


def _strip_newlines(value: str) -> str:
    """Verwijder CR/LF zodat client-input geen valse logregels kan injecteren (text-logformat)."""
    return value.replace("\r", " ").replace("\n", " ")


@app.post("/api/client-log")
async def client_log(request: Request):
    """Frontend-foutrapportage: de ErrorBoundary stuurt hier render-fouten naartoe,
    zodat ze in de server-logs verschijnen (met request-id), zonder externe reporter."""
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_CLIENT_LOG_BYTES:
        return Response(status_code=413)
    raw = await request.body()
    if len(raw) > _MAX_CLIENT_LOG_BYTES:
        return Response(status_code=413)
    try:
        import json as _json
        body = _json.loads(raw) if raw else {}
        if not isinstance(body, dict):
            body = {}
    except Exception:
        body = {}
    message = _strip_newlines(str(body.get("message", ""))[:500])
    url = _strip_newlines(str(body.get("url", ""))[:300])
    stack = _strip_newlines(str(body.get("stack", ""))[:2000])
    logger.warning("Frontend-fout: %s | url=%s | stack=%s", message, url, stack)
    return Response(status_code=204)


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # Resolve en controleer dat het pad binnen STATIC_DIR blijft, zodat een
        # verzoek als /../../etc/passwd geen bestanden buiten de map kan lekken.
        requested = (STATIC_DIR / path).resolve()
        if requested.is_file() and requested.is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(requested)
        # Onbekend pad -> SPA-fallback (client-side routing handelt het af).
        return FileResponse(STATIC_DIR / "index.html")
