import logging
from contextlib import asynccontextmanager

import asyncpg

from backend.config import Settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(settings: Settings) -> None:
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=5,
            max_size=20,
            command_timeout=25,
            timeout=5,
        )
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
