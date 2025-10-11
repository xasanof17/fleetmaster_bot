"""
services/group_map.py
Handles database interactions for truck ↔ group mapping.
"""

import asyncpg
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from config.settings import settings
from utils.logger import get_logger
from config.db import get_pool 

logger = get_logger(__name__)

# ----------------------------------------------------------------
# Connection pool
# ----------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    """Initialize the async Postgres connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )
        logger.info("🟢 Database pool initialized successfully.")
        await ensure_table_exists()
        return _pool
    except Exception as e:
        logger.error(f"❌ Failed to initialize DB pool: {e}")
        raise


async def ensure_table_exists():
    """Ensure the truck_groups table exists."""
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS truck_groups (
                unit TEXT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
        )
    logger.info("✅ Verified truck_groups table.")


# ----------------------------------------------------------------
# Core CRUD
# ----------------------------------------------------------------
async def upsert_mapping(unit: str, chat_id: int, title: str):
    pool = await get_pool()
    query = """
    INSERT INTO public.truck_groups (unit, chat_id, title)
    VALUES ($1, $2, $3)
    ON CONFLICT (unit) DO UPDATE
    SET chat_id = EXCLUDED.chat_id,
        title = EXCLUDED.title,
        created_at = NOW();
    """
    async with pool.acquire() as conn:
        await conn.execute(query, unit, chat_id, title)
    logger.info(f"✅ Updated mapping: {unit} → {chat_id} ({title})")



async def get_truck_group(unit: str) -> Optional[Dict[str, Any]]:
    """Fetch a single truck group mapping by unit."""
    pool = await init_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT * FROM truck_groups WHERE unit = $1", unit
            )
            if row:
                return dict(row)
        except Exception as e:
            logger.error(f"⚠️ Error fetching truck group {unit}: {e}")
    return None


async def list_all_groups():
    pool = await get_pool()
    query = "SELECT unit, chat_id, title, created_at FROM public.truck_groups ORDER BY created_at DESC"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [dict(r) for r in rows]


# ----------------------------------------------------------------
# Quick lookup helper for handlers
# ----------------------------------------------------------------
async def get_group_id_for_unit(unit: str) -> Optional[int]:
    """
    Returns the Telegram chat_id for a given truck unit, or None if not found.
    """
    try:
        pool = await init_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT chat_id FROM truck_groups WHERE unit = $1", unit)
            if row:
                logger.info(f"🎯 Found group for unit {unit}: {row['chat_id']}")
                return row["chat_id"]
            else:
                logger.warning(f"⚠️ No group found in DB for unit {unit}")
                return None
    except Exception as e:
        logger.error(f"💥 DB lookup failed for {unit}: {e}")
        return None


# ----------------------------------------------------------------
# Graceful cleanup
# ----------------------------------------------------------------
async def close_pool():
    """Close connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("🟡 Database pool closed.")


# ----------------------------------------------------------------
# Synchronous helper for external modules (optional)
# ----------------------------------------------------------------
def sync_upsert(unit: str, chat_id: int, title: str):
    """Helper to allow synchronous scripts to add mappings."""
    asyncio.run(upsert_mapping(unit, chat_id, title))
