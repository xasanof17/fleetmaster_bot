"""
services/group_map.py
FleetMaster — Truck/Group Mapping Database Layer
SAFE • MODERN • PRODUCTION READY

Identity rules:
    ✅ chat_id is the stable primary identity (Telegram group ID never changes)
    ✅ unit/driver/phone/title are parsed values that may change over time

This version:
    - Auto-creates/migrates table
    - NEVER deletes links automatically
    - Safe UPSERT by chat_id (PK)
    - Optional unique unit (nullable)
    - Minimal logs (prod-only) + always log errors
"""

from __future__ import annotations

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
        # ✅ chat_id is PK; unit is optional/unique (nullable)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public.truck_groups (
                chat_id BIGINT PRIMARY KEY,
                unit TEXT UNIQUE,
                title TEXT NOT NULL,
                raw_title TEXT,
                driver_name TEXT,
                phone_number TEXT,
                driver_is_new BOOLEAN DEFAULT FALSE,
                active BOOLEAN DEFAULT TRUE,
                last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )

        # Safe migrations (idempotent)
        await conn.execute("ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS unit TEXT;")
        await conn.execute("ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS title TEXT;")
        await conn.execute("ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS raw_title TEXT;")
        await conn.execute("ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS driver_name TEXT;")
        await conn.execute("ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS phone_number TEXT;")
        await conn.execute(
            "ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS driver_is_new BOOLEAN DEFAULT FALSE;"
        )
        await conn.execute(
            "ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;"
        )
        await conn.execute(
            "ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW();"
        )
        await conn.execute(
            "ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();"
        )
        await conn.execute(
            "ALTER TABLE truck_groups ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();"
        )

        # ✅ Ensure unique(unit) exists but allows NULLs
        # Postgres UNIQUE allows multiple NULLs; that’s exactly what we want.
        await conn.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname = 'truck_groups_unit_unique_idx'
                ) THEN
                    CREATE UNIQUE INDEX truck_groups_unit_unique_idx
                    ON public.truck_groups (unit);
                END IF;
            END $$;
            """
        )

    if not _TABLE_READY:
        _info("DB ready: truck_groups")
        _TABLE_READY = True


# ============================================================
# UPSERT MAPPING (BY CHAT_ID)
# ============================================================
async def upsert_mapping(
    unit: str | None,
    chat_id: int,
    title: str,
    driver_name: str | None = None,
    phone_number: str | None = None,
    driver_is_new: bool = False,
    driver_status: str = "ACTIVE",
    active: bool = True,
    raw_title: str | None = None,
) -> dict[str, Any]:
    if not chat_id:
        _warning("upsert_mapping called with empty chat_id")
        return {"created": False, "changed": False, "changed_fields": []}

    await ensure_table()
    pool = await get_pool()

    unit_val = (unit or "").strip() or None
    title_val = (title or "").strip() or "UNKNOWN"
    raw_title_val = raw_title if raw_title is not None else title_val

    async with pool.acquire() as conn:
        try:
            existing = await conn.fetchrow(
                """
                SELECT unit, title, driver_name, phone_number,
                       driver_is_new, driver_status, active
                FROM truck_groups
                WHERE chat_id=$1
                """,
                chat_id,
            )

            if existing:
                changed: list[str] = []

                def diff(col, new):
                    if (existing[col] or None) != (new or None):
                        changed.append(col)

                diff("unit", unit_val)
                diff("title", title_val)
                diff("driver_name", driver_name)
                diff("phone_number", phone_number)

                if bool(existing["driver_is_new"]) != bool(driver_is_new):
                    changed.append("driver_is_new")

                if existing["driver_status"] != driver_status:
                    changed.append("driver_status")

                if bool(existing["active"]) != bool(active):
                    changed.append("active")

                if not changed:
                    await conn.execute(
                        "UPDATE truck_groups SET last_seen_at=NOW() WHERE chat_id=$1",
                        chat_id,
                    )
                    return {"created": False, "changed": False, "changed_fields": []}

                await conn.execute(
                    """
                    UPDATE truck_groups
                    SET
                        unit=$2,
                        title=$3,
                        raw_title=$4,
                        driver_name=$5,
                        phone_number=$6,
                        driver_is_new=$7,
                        driver_status=$8,
                        active=$9,
                        last_seen_at=NOW(),
                        updated_at=NOW()
                    WHERE chat_id=$1
                    """,
                    chat_id,
                    unit_val,
                    title_val,
                    raw_title_val,
                    driver_name,
                    phone_number,
                    driver_is_new,
                    driver_status,
                    active,
                )

                return {"created": False, "changed": True, "changed_fields": changed}

            # create new
            await conn.execute(
                """
                INSERT INTO truck_groups
                (chat_id, unit, title, raw_title,
                 driver_name, phone_number,
                 driver_is_new, driver_status,
                 active, last_seen_at, created_at, updated_at)
                VALUES
                ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW(),NOW(),NOW())
                """,
                chat_id,
                unit_val,
                title_val,
                raw_title_val,
                driver_name,
                phone_number,
                driver_is_new,
                driver_status,
                active,
            )

            return {"created": True, "changed": True, "changed_fields": ["created"]}

        except Exception as e:
            _error(f"UPSERT FAILED chat={chat_id}: {e}")
            return {"created": False, "changed": False, "changed_fields": ["error"]}


# ============================================================
# READ HELPERS
# ============================================================
async def get_group_by_chat(chat_id: int) -> dict[str, Any] | None:
    await ensure_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE chat_id=$1", chat_id)
        return dict(row) if row else None


async def get_truck_group(unit: str) -> dict[str, Any] | None:
    if not unit:
        return None
    await ensure_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM truck_groups WHERE unit=$1", unit.strip())
        return dict(row) if row else None


async def get_group_id_for_unit(unit: str) -> int | None:
    rec = await get_truck_group(unit)
    return int(rec["chat_id"]) if rec else None


async def list_all_groups(active_only: bool = False) -> list[dict[str, Any]]:
    await ensure_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        if active_only:
            rows = await conn.fetch(
                "SELECT * FROM truck_groups WHERE active=true ORDER BY updated_at DESC"
            )
        else:
            rows = await conn.fetch("SELECT * FROM truck_groups ORDER BY updated_at DESC")
        return [dict(r) for r in rows]


# ============================================================
# SAFETY — MANUAL REMOVE ONLY
# ============================================================
async def unlink_chat(chat_id: int):
    await ensure_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            res = await conn.execute("DELETE FROM truck_groups WHERE chat_id=$1", chat_id)
            _info(f"Unlinked chat={chat_id} ({res})")
        except Exception as e:
            _error(f"unlink_chat FAILED chat={chat_id}: {e}")


# ============================================================
# SANITY CHECK (read-only)
# ============================================================
async def verify_all_mappings():
    await ensure_table()
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM truck_groups")

        report = {
            "total": len(rows),
            "missing_unit": 0,
            "missing_driver": 0,
            "missing_phone": 0,
            "inactive": 0,
        }

        for r in rows:
            if not r.get("unit"):
                report["missing_unit"] += 1
            if not r.get("driver_name"):
                report["missing_driver"] += 1
            if not r.get("phone_number"):
                report["missing_phone"] += 1
            if not r.get("active"):
                report["inactive"] += 1

        _info(f"SanityCheck: {report}")
        return report


# ============================================================
# CLOSE POOL
# ============================================================
async def close_pool():
    pool = await get_pool()
    try:
        await pool.close()
        _info("DB pool closed")
    except Exception as e:
        _error(f"db close failed: {e}")
