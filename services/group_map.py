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

import asyncpg
from typing import Optional, Dict, Any, List
from config.settings import settings
from utils.logger import get_logger
from config.db import get_pool

logger = get_logger(__name__)


# ============================================================
# TABLE SETUP & MIGRATION
# ============================================================
async def ensure_table():
    """Create required table + add missing columns safely."""
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

    logger.info("🟢 DB migrations OK — truck_groups ready.")


# ============================================================
# UPSERT MAPPING
# ============================================================
async def upsert_mapping(
    unit: Optional[str],
    chat_id: int,
    title: str,
    driver_name: Optional[str] = None,
    phone_number: Optional[str] = None,
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
        logger.warning("⚠️ upsert_mapping called with empty chat_id!")
        return

    await ensure_table()
    pool = await get_pool()

    unit_val = unit or f"CHAT_{chat_id}"

    async with pool.acquire() as conn:
        try:
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
                unit_val, chat_id, title, driver_name, phone_number
            )

            logger.info(
                f"🔄 UPSERT OK — {unit_val} → chat {chat_id} | driver={driver_name}, phone={phone_number}"
            )

        except Exception as e:
            logger.error(f"💥 UPSERT FAILED: {e}")


# ============================================================
# READ HELPERS
# ============================================================
async def get_truck_group(unit: str) -> Optional[Dict[str, Any]]:
    """Return full record for given truck unit."""
    if not unit:
        return None

    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE unit=$1", unit)
        return dict(row) if row else None


async def get_group_by_chat(chat_id: int) -> Optional[Dict[str, Any]]:
    """Return record by Telegram chat_id."""
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE chat_id=$1", chat_id)
        return dict(row) if row else None


async def get_group_id_for_unit(unit: str) -> Optional[int]:
    """Return chat_id for unit."""
    rec = await get_truck_group(unit)
    return rec["chat_id"] if rec else None


async def list_all_groups() -> List[Dict[str, Any]]:
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
            logger.info(f"🗑️ Manual unlink → chat={chat_id} ({res})")
        except Exception as e:
            logger.error(f"❌ unlink_chat FAILED: {e}")


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

        logger.info(f"🧠 Mapping Sanity Check → {report}")
        return report


# ============================================================
# CLOSE POOL
# ============================================================
async def close_pool():
    pool = await get_pool()
    try:
        await pool.close()
        logger.info("🟡 DB pool closed safely.")
    except Exception as e:
        logger.error(f"❌ db close failed: {e}")
