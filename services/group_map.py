"""
services/group_map.py
FleetMaster — Truck/Group Mapping Database Layer
SAFE • MODERN • PRODUCTION READY

Handles:
    • unit (truck number)
    • chat_id (telegram group id)
    • title (group title)
    • driver_name
    • phone_number
    • created_at
    • updated_at

This version:
    - Auto-creates/migrates table
    - NEVER deletes links automatically
    - Fast UPSERT (unit is PK)
    - Safe read helpers
    - Clean consistent API
"""

from typing import Any

from config.db import get_pool
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# LOGGING CONTROL (NO FLOOD)
# ============================================================
# Only log INFO/WARNING in production. Errors always log.
_LOG_INFO_ENABLED = str(getattr(settings, "ENV", "")).lower() in {"prod", "production"}


def _info(msg: str):
    if _LOG_INFO_ENABLED:
        logger.info(msg)


def _warning(msg: str):
    if _LOG_INFO_ENABLED:
        logger.warning(msg)


def _error(msg: str):
    # Always keep errors visible
    logger.error(msg)


# Ensure table logs only once per process
_TABLE_READY = False


# ============================================================
# TABLE SETUP & MIGRATION
# ============================================================
async def ensure_table():
    """Create required table + add missing columns safely."""
    global _TABLE_READY
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Create table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.truck_groups (
                unit TEXT PRIMARY KEY,
                chat_id BIGINT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                driver_name TEXT,
                phone_number TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Add missing columns (safe)
        await conn.execute("""
            ALTER TABLE truck_groups
            ADD COLUMN IF NOT EXISTS driver_name TEXT;
        """)

        await conn.execute("""
            ALTER TABLE truck_groups
            ADD COLUMN IF NOT EXISTS phone_number TEXT;
        """)

        await conn.execute("""
            ALTER TABLE truck_groups
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
        """)

    # ✅ only log this once, and only in prod
    if not _TABLE_READY:
        _info("DB ready: truck_groups")
        _TABLE_READY = True


# ============================================================
# UPSERT MAPPING
# ============================================================
async def upsert_mapping(
    unit: str | None,
    chat_id: int,
    title: str,
    driver_name: str | None = None,
    phone_number: str | None = None,
):
    """
    Insert or update truck-group mapping.

    Rules:
        - unit is PRIMARY KEY
        - updates chat_id + title ALWAYS
        - driver_name/phone update only if provided
        - updated_at ALWAYS refreshed
        - never deletes groups automatically
    """
    if not chat_id:
        # ✅ no warnings in dev, only prod
        _warning("upsert_mapping called with empty chat_id")
        return

    await ensure_table()
    pool = await get_pool()

    unit_val = unit or f"CHAT_{chat_id}"

    async with pool.acquire() as conn:
        try:
            # ✅ Read current mapping to avoid spam logging
            existing = await conn.fetchrow(
                "SELECT chat_id FROM truck_groups WHERE unit=$1",
                unit_val
            )

            await conn.execute(
                """
                INSERT INTO truck_groups
                    (unit, chat_id, title, driver_name, phone_number, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (unit) DO UPDATE SET
                    chat_id = EXCLUDED.chat_id,
                    title = EXCLUDED.title,
                    driver_name = COALESCE(EXCLUDED.driver_name, truck_groups.driver_name),
                    phone_number = COALESCE(EXCLUDED.phone_number, truck_groups.phone_number),
                    updated_at = NOW();
                """,
                unit_val,
                chat_id,
                title,
                driver_name,
                phone_number,
            )

            # ✅ Log ONLY important events (prod only)
            if not existing:
                _info(f"Linked: {unit_val} -> {chat_id}")
            elif int(existing["chat_id"]) != int(chat_id):
                _warning(f"Relinked: {unit_val} {existing['chat_id']} -> {chat_id}")

        except Exception as e:
            _error(f"UPSERT FAILED for unit={unit_val}, chat={chat_id}: {e}")


# ============================================================
# READ HELPERS
# ============================================================
async def get_truck_group(unit: str) -> dict[str, Any] | None:
    """Return full record for given truck unit."""
    if not unit:
        return None

    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE unit=$1", unit)
        return dict(row) if row else None


async def get_group_by_chat(chat_id: int) -> dict[str, Any] | None:
    """Return record by Telegram chat_id."""
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE chat_id=$1", chat_id)
        return dict(row) if row else None


async def get_group_id_for_unit(unit: str) -> int | None:
    """Return chat_id for unit."""
    rec = await get_truck_group(unit)
    return rec["chat_id"] if rec else None


async def list_all_groups() -> list[dict[str, Any]]:
    """Return all groups sorted newest first."""
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM truck_groups
            ORDER BY updated_at DESC;
        """)
        return [dict(r) for r in rows]


# ============================================================
# SAFETY — MANUAL REMOVE ONLY
# ============================================================
async def unlink_chat(chat_id: int):
    """Manual unlink (never used automatically)."""
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        try:
            res = await conn.execute("DELETE FROM truck_groups WHERE chat_id=$1", chat_id)
            # ✅ short + prod only
            _info(f"Unlinked chat={chat_id} ({res})")
        except Exception as e:
            _error(f"unlink_chat FAILED for chat={chat_id}: {e}")


# ============================================================
# SANITY CHECK (read-only)
# ============================================================
async def verify_all_mappings():
    """Check for duplicates or invalid mappings."""
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM truck_groups")

        report = {
            "total": len(rows),
            "empty_units": 0,
            "missing_driver": 0,
            "duplicates": 0,
        }

        seen_units = set()

        for r in rows:
            if not r["unit"] or r["unit"].startswith("CHAT_"):
                report["empty_units"] += 1

            if not r["driver_name"]:
                report["missing_driver"] += 1

            if r["unit"] in seen_units:
                report["duplicates"] += 1
            else:
                seen_units.add(r["unit"])

        # ✅ keep but make it non-flooding (prod only)
        _info(f"SanityCheck: {report}")
        return report


# ============================================================
# CLOSE POOL
# ============================================================
async def close_pool():
    pool = await get_pool()
    try:
        await pool.close()
        # ✅ prod only
        _info("DB pool closed")
    except Exception as e:
        _error(f"db close failed: {e}")
