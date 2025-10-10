"""
services/group_map.py
Dynamic Truck → Telegram Group mapping (PostgreSQL-based)
Compatible with both async DB access and legacy imports
"""
import asyncpg
from typing import Optional, Dict, List
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)
DB_URL = settings.DATABASE_URL


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────
async def _get_connection():
    try:
        return await asyncpg.connect(DB_URL)
    except Exception as e:
        logger.error(f"❌ DB connection failed: {e}")
        return None


async def _ensure_table(conn):
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS truck_groups (
                unit TEXT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                group_title TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Error ensuring table: {e}")


# ─────────────────────────────────────────────
# MAIN DB FUNCTIONS
# ─────────────────────────────────────────────
async def get_group_id_for_unit(unit: str) -> Optional[int]:
    conn = await _get_connection()
    if not conn:
        return None
    try:
        await _ensure_table(conn)
        row = await conn.fetchrow("SELECT chat_id FROM truck_groups WHERE unit=$1;", str(unit))
        return int(row["chat_id"]) if row else None
    except Exception as e:
        logger.error(f"Error fetching group for {unit}: {e}")
        return None
    finally:
        await conn.close()


async def upsert_mapping(unit: str, chat_id: int, title: str = "") -> bool:
    conn = await _get_connection()
    if not conn:
        return False
    try:
        await _ensure_table(conn)
        await conn.execute("""
            INSERT INTO truck_groups (unit, chat_id, group_title, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (unit) DO UPDATE
            SET chat_id=EXCLUDED.chat_id,
                group_title=EXCLUDED.group_title,
                updated_at=NOW();
        """, str(unit), int(chat_id), title or "")
        logger.info(f"✅ Linked truck {unit} → group {chat_id} ({title})")
        return True
    except Exception as e:
        logger.error(f"❌ upsert_mapping failed: {e}")
        return False
    finally:
        await conn.close()


async def list_all_groups() -> List[Dict[str, str]]:
    conn = await _get_connection()
    if not conn:
        return []
    try:
        await _ensure_table(conn)
        rows = await conn.fetch("SELECT * FROM truck_groups;")
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        return []
    finally:
        await conn.close()


async def remove_mapping(unit: str) -> bool:
    conn = await _get_connection()
    if not conn:
        return False
    try:
        await _ensure_table(conn)
        result = await conn.execute("DELETE FROM truck_groups WHERE unit=$1;", str(unit))
        return result.startswith("DELETE")
    except Exception as e:
        logger.error(f"Error removing mapping: {e}")
        return False
    finally:
        await conn.close()


# ─────────────────────────────────────────────
# LEGACY SUPPORT (for imports like load_truck_groups)
# ─────────────────────────────────────────────
async def load_truck_groups() -> Dict[str, int]:
    """
    Legacy helper for backward compatibility.
    Loads all truck→group mappings as a dict {unit: chat_id}.
    """
    try:
        data = await list_all_groups()
        result = {row["unit"]: int(row["chat_id"]) for row in data if "unit" in row and "chat_id" in row}
        logger.info(f"✅ Loaded {len(result)} truck→group mappings from DB.")
        return result
    except Exception as e:
        logger.error(f"Error in load_truck_groups: {e}")
        return {}
