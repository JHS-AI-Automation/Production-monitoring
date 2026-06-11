import asyncio
import logging
import time
from contextlib import asynccontextmanager

import asyncpg

from backend.config import Settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# Voor lazy reconnect (stroomuitval-scenario op de IXrouter: Postgres komt later op
# dan het dashboard, of valt tussentijds weg). get_connection() probeert dan met
# backoff de pool opnieuw op te bouwen; de Docker-healthcheck (elke 30s op
# /api/health) drijft het herstel ook zonder gebruikersverkeer aan.
_settings: Settings | None = None
_last_attempt: float = float("-inf")
_RETRY_INTERVAL_SECONDS = 30
_reconnect_lock = asyncio.Lock()

# Pool-instellingen. command_timeout kapt vastgelopen queries af, timeout begrenst
# hoe lang acquire() op een vrije connectie wacht.
_COMMAND_TIMEOUT = 25
_CONNECT_TIMEOUT = 5


async def create_db_pool(
    settings: Settings,
    *,
    user: str | None = None,
    password: str | None = None,
    min_size: int = 5,
    max_size: int = 20,
) -> asyncpg.Pool:
    """Maak een asyncpg-pool naar dezelfde database.

    `user`/`password` overschrijven de hoofd-credentials (gebruikt door de chat-router
    voor een aparte read-only rol). Dit is de enige plek waar een pool wordt gemaakt,
    zodat host/poort/timeouts niet op twee plekken uit elkaar lopen.
    """
    return await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=user or settings.db_user,
        password=password or settings.db_password,
        min_size=min_size,
        max_size=max_size,
        command_timeout=_COMMAND_TIMEOUT,
        timeout=_CONNECT_TIMEOUT,
    )


async def init_pool(settings: Settings) -> None:
    global _pool, _settings
    _settings = settings
    try:
        _pool = await create_db_pool(settings)
        logger.info("Database pool created (%s:%s/%s)", settings.db_host, settings.db_port, settings.db_name)
    except Exception:
        logger.warning(
            "Database niet bereikbaar (%s:%s) - dashboard start zonder DB, "
            "reconnect-pogingen volgen met %ds backoff",
            settings.db_host, settings.db_port, _RETRY_INTERVAL_SECONDS,
        )
        _pool = None


async def close_pool() -> None:
    global _pool, _settings
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")
    _settings = None


async def _try_reconnect() -> None:
    """Bouw de pool lazy opnieuw op, maximaal eens per _RETRY_INTERVAL_SECONDS.

    Het lock voorkomt dat gelijktijdige requests allemaal tegelijk een pool
    proberen op te zetten; de backoff voorkomt dat een onbereikbare DB elke
    request met een connect-timeout (5s) belast.
    """
    global _pool, _last_attempt
    async with _reconnect_lock:
        if _pool is not None or _settings is None:
            return
        now = time.monotonic()
        if now - _last_attempt < _RETRY_INTERVAL_SECONDS:
            return
        _last_attempt = now
        try:
            _pool = await create_db_pool(_settings)
            logger.info(
                "Database pool hersteld (%s:%s/%s)",
                _settings.db_host, _settings.db_port, _settings.db_name,
            )
        except Exception:
            logger.warning(
                "Reconnect naar database mislukt (%s:%s); volgende poging over %ds",
                _settings.db_host, _settings.db_port, _RETRY_INTERVAL_SECONDS,
            )


@asynccontextmanager
async def get_connection():
    if _pool is None:
        await _try_reconnect()
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.acquire() as conn:
        yield conn


async def check_health() -> bool:
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        logger.exception("Health check failed")
        return False


def pool_stats() -> dict | None:
    """Momentopname van de connection-pool, voor /api/health en /api/metrics."""
    if _pool is None:
        return None
    size = _pool.get_size()
    idle = _pool.get_idle_size()
    return {
        "min_size": _pool.get_min_size(),
        "max_size": _pool.get_max_size(),
        "size": size,
        "idle": idle,
        "in_use": size - idle,
    }
