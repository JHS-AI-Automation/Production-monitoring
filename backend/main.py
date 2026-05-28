import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.database import check_health, close_pool, init_pool
from backend.routers.alarms import router as alarms_router
from backend.routers.chat import router as chat_router, init_chat, close_chat_pool
from backend.routers.pallets import router as pallets_router
from backend.routers.production import router as production_router

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _setup_logging() -> None:
    import json
    from datetime import datetime, timezone
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
                "message": record.getMessage(),
            }
            if record.exc_info and record.exc_info[1]:
                entry["error_type"] = type(record.exc_info[1]).__name__
                entry["traceback"] = traceback.format_exception(*record.exc_info)
            return json.dumps(entry, ensure_ascii=False, default=str)

    text_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.root.handlers.clear()
    logging.root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console.setFormatter(JSONFormatter())
    else:
        console.setFormatter(text_formatter)
    logging.root.addHandler(console)

    # 5MB per bestand, 5 bestanden bewaard = max 25MB logs
    file_handler = RotatingFileHandler(
        log_dir / "dashboard.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    logging.root.addHandler(file_handler)


_setup_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    await init_pool(settings)
    await init_chat(settings.openrouter_api_key, settings.chat_model)
    logger.info("Optimax started on %s:%s", settings.app_host, settings.app_port)
    yield
    await close_chat_pool()
    await close_pool()


app = FastAPI(title="Optimax", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time as _time

    start = _time.monotonic()
    try:
        response = await call_next(request)
        duration_ms = round((_time.monotonic() - start) * 1000)
        if response.status_code >= 400:
            logger.warning(
                "%s %s -> %d (%dms)",
                request.method, request.url.path, response.status_code, duration_ms,
            )
        return response
    except Exception:
        duration_ms = round((_time.monotonic() - start) * 1000)
        logger.exception(
            "Unhandled error: %s %s (%dms)", request.method, request.url.path, duration_ms,
        )
        return JSONResponse({"detail": "Internal server error"}, status_code=500)


app.include_router(alarms_router)
app.include_router(production_router)
app.include_router(pallets_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    db_ok = await check_health()
    status = "healthy" if db_ok else "unhealthy"
    code = 200 if db_ok else 503
    return JSONResponse({"status": status, "database": db_ok}, status_code=code)


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = STATIC_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
