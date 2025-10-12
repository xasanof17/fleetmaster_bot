"""
services/group_map.py
Handles database interactions for truck ↔ group mapping.
SAFE VERSION ✅ Keeps unlink_chat() for compatibility and removes auto-cleanup.
"""

import asyncpg
import asyncio
from typing import Optional, Dict, Any, List
from config.settings import settings
from utils.logger import get_logger
from config.db import get_pool

logger = get_logger(__name__)

_pool: Optional[asyncpg.Pool] = None


# ----------------------------------------------------------------
# CONNECTION
# ----------------------------------------------------------------
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
    pool = await init_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS truck_groups (
                unit TEXT PRIMARY KEY,
                chat_id BIGINT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
        )
    logger.info("✅ Verified truck_groups table.")


# ----------------------------------------------------------------
# CORE CRUD
# ----------------------------------------------------------------
async def upsert_mapping(unit: Optional[str], chat_id: int, title: str):
    """Insert or update mapping between a truck unit and Telegram group."""
    if not chat_id:
        logger.warning("⚠️ upsert_mapping called without chat_id — skipped.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            unit_value = unit or f"CHAT_{chat_id}"
            query = """
            INSERT INTO public.truck_groups (unit, chat_id, title)
            VALUES ($1, $2, $3)
            ON CONFLICT (unit) DO UPDATE
            SET chat_id = EXCLUDED.chat_id,
                title = EXCLUDED.title,
                created_at = NOW();
            """
            await conn.execute(query, unit_value, chat_id, title)
            logger.info(f"✅ Updated mapping: {unit_value} → {chat_id} ({title})")
        except Exception as e:
            logger.error(f"💥 DB upsert failed for unit={unit}, chat={chat_id}: {e}")


async def unlink_chat(chat_id: int):
    """Remove mapping for a chat when bot is removed or kicked (safe, manual only)."""
    if not chat_id:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            result = await conn.execute("DELETE FROM public.truck_groups WHERE chat_id = $1", chat_id)
            if result and "DELETE" in result:
                logger.info(f"🗑️ Unlinked chat {chat_id} from DB.")
            else:
                logger.warning(f"⚠️ No mapping found to unlink for chat {chat_id}.")
        except Exception as e:
            logger.error(f"💥 Failed to unlink chat {chat_id}: {e}")


async def get_truck_group(unit: str) -> Optional[Dict[str, Any]]:
    """Fetch a single truck group mapping by unit."""
    pool = await init_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT * FROM truck_groups WHERE unit = $1", unit)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"⚠️ Error fetching truck group {unit}: {e}")
    return None


async def list_all_groups() -> List[Dict[str, Any]]:
    """List all known truck-group mappings."""
    pool = await get_pool()
    query = "SELECT unit, chat_id, title, created_at FROM public.truck_groups ORDER BY created_at DESC"
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"💥 Failed to list groups: {e}")
            return []


async def get_group_id_for_unit(unit: str) -> Optional[int]:
    """Returns the Telegram chat_id for a given truck unit."""
    if not unit:
        return None
    try:
        pool = await init_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT chat_id FROM truck_groups WHERE unit = $1", unit)
            if row:
                chat_id = row["chat_id"]
                logger.info(f"🎯 Found group for unit {unit}: {chat_id}")
                return chat_id
            else:
                logger.warning(f"⚠️ No group found for unit {unit}")
                return None
    except Exception as e:
        logger.error(f"💥 DB lookup failed for {unit}: {e}")
        return None


# ----------------------------------------------------------------
# SANITY CHECKER 🧠 (Read-Only)
# ----------------------------------------------------------------
async def verify_all_mappings():
    """
    Scan DB for duplicates, nulls, or inconsistencies.
    Safe: does not delete or modify anything automatically.
    """
    pool = await get_pool()
    report = {"total": 0, "duplicates": [], "null_units": [], "invalid_chats": []}

    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch("SELECT unit, chat_id, title FROM public.truck_groups")
            report["total"] = len(rows)

            seen_chats = {}
            for row in rows:
                unit, chat_id = row["unit"], row["chat_id"]

                if not unit or unit.startswith("CHAT_"):
                    report["null_units"].append(dict(row))
                if chat_id in seen_chats:
                    report["duplicates"].append((seen_chats[chat_id], unit))
                else:
                    seen_chats[chat_id] = unit

            logger.info(
                f"🧾 Sanity check done: total={report['total']}, "
                f"duplicates={len(report['duplicates'])}, "
                f"nulls={len(report['null_units'])}"
            )
        except Exception as e:
            logger.error(f"💥 verify_all_mappings failed: {e}")

    return report


# ----------------------------------------------------------------
# SAFE STARTUP SCANNER 🚫 No Cleanup
# ----------------------------------------------------------------
async def verify_existing_groups(bot):
    """
    Scan and refresh all known groups on bot startup.
    Does NOT delete or clean any records. Logs only.
    """
    await init_pool()
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT unit, chat_id, title FROM public.truck_groups")
        logger.info(f"🔍 Checking {len(rows)} stored group mappings...")

        verified, unreachable = 0, 0

        for row in rows:
            unit, chat_id, title = row["unit"], row["chat_id"], row["title"]

            try:
                chat = await bot.get_chat(chat_id)
                if chat and chat.title != title:
                    await conn.execute(
                        "UPDATE public.truck_groups SET title=$1 WHERE chat_id=$2",
                        chat.title, chat_id
                    )
                    logger.info(f"🔁 Updated title for {unit} → {chat.title}")
                verified += 1
            except Exception as e:
                logger.warning(f"⚠️ Unreachable group ({chat_id}, {title}): {e}")
                unreachable += 1

        logger.info(f"✅ Group scan done — Verified={verified}, Unreachable={unreachable}")


# ----------------------------------------------------------------
# CLOSE POOL
# ----------------------------------------------------------------
async def close_pool():
    """Close database pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("🟡 Database pool closed.")


# ----------------------------------------------------------------
# SYNC HELPER
# ----------------------------------------------------------------
def sync_upsert(unit: str, chat_id: int, title: str):
    """Sync helper to add mappings manually."""
    asyncio.run(upsert_mapping(unit, chat_id, title))
