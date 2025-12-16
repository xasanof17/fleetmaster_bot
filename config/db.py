import asyncio
import os
import ssl

import asyncpg
from dotenv import load_dotenv

from utils.logger import get_logger

load_dotenv()

logger = get_logger("db")

_POOL: asyncpg.Pool | None = None
_POOL_LOCK = asyncio.Lock()  # Prevents race conditions during lazy init


# ============================================================
# INTERNAL: CREATE POOL
# ============================================================
async def _create_pool() -> asyncpg.Pool:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    try:
        # Some Railway/hosted DBs need 'sslmode=require' but
        # Python's ssl module needs a context to handle it correctly.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=2,  # Increased slightly for background tasks + bot
            max_size=10,  # Scaled up for better concurrency
            max_queries=50000,  # Recycle connections to prevent memory leaks
            timeout=10,
            command_timeout=30,
            ssl=ctx,  # Use the custom SSL context
        )

        # Verify connection immediately
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")

        logger.info("✅ PostgreSQL pool created and verified")
        return pool

    except Exception as e:
        logger.error(f"❌ Failed to create PostgreSQL pool: {e}")
        raise


# ============================================================
# PUBLIC API
# ============================================================
async def init_db():
    """
    Explicit DB init. Safe to call multiple times.
    """
    global _POOL
    async with _POOL_LOCK:
        if _POOL is None:
            _POOL = await _create_pool()


async def get_pool() -> asyncpg.Pool:
    """
    Lazy pool getter with concurrency lock.
    """
    global _POOL
    if _POOL is None:
        async with _POOL_LOCK:
            if _POOL is None:  # Double-check pattern
                _POOL = await _create_pool()
    return _POOL


async def close_pool():
    """
    Gracefully close DB pool.
    """
    global _POOL
    async with _POOL_LOCK:
        if _POOL is not None:
            # wait_until_finish=True ensures active queries finish before closing
            await asyncio.wait_for(_POOL.close(), timeout=5.0)
            _POOL = None
            logger.info("🟡 PostgreSQL pool closed")
