import os

import asyncpg
from dotenv import load_dotenv

from utils.logger import get_logger

load_dotenv()

logger = get_logger("db")

_POOL: asyncpg.Pool | None = None


# ============================================================
# INTERNAL: CREATE POOL
# ============================================================
async def _create_pool() -> asyncpg.Pool:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    try:
        pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=1,
            max_size=5,
            timeout=10,
            command_timeout=30,
            ssl="require",  # REQUIRED for Railway
        )

        logger.info("✅ PostgreSQL pool created")
        return pool

    except Exception as e:
        logger.error(f"❌ Failed to create PostgreSQL pool: {e}")
        raise


# ============================================================
# PUBLIC API
# ============================================================
async def init_db():
    """
    Explicit DB init (optional).
    Safe to call multiple times.
    """
    global _POOL

    if _POOL is None:
        _POOL = await _create_pool()


async def get_pool() -> asyncpg.Pool:
    """
    Lazy pool getter.
    ALWAYS returns a valid pool or raises.
    """
    global _POOL

    if _POOL is None:
        _POOL = await _create_pool()

    return _POOL


async def close_pool():
    """
    Gracefully close DB pool.
    """
    global _POOL

    if _POOL is not None:
        await _POOL.close()
        _POOL = None
        logger.info("🟡 PostgreSQL pool closed")
