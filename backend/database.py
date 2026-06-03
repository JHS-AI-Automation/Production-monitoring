import logging
from contextlib import asynccontextmanager

import asyncpg

from backend.config import Settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

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
    global _pool
    try:
        _pool = await create_db_pool(settings)
        logger.info("Database pool created (%s:%s/%s)", settings.db_host, settings.db_port, settings.db_name)
    except Exception:
        logger.warning("Database niet bereikbaar (%s:%s) - dashboard start zonder DB", settings.db_host, settings.db_port)
        _pool = None


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


@asynccontextmanager
async def get_connection():
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
