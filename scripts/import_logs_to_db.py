"""
scripts/import_logs_to_db.py
Rebuilds truck_groups DB table from log history.
✅ Extracts unit, chat_id, title from logs.json
✅ Adds 'active' = TRUE automatically
✅ Auto-expands title column to TEXT (no truncation)
"""

import sys, os, json, re, asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # make imports work

from services.group_map import init_pool
from utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger("log_importer")

# 🔍 Match messages like: Linked Truck 2054 → Chat -4860500008 (2054 - Mr. Azamat 🟢 ...)
LINK_RE = re.compile(
    r"Linked Truck\s+(\d{3,5})\s*→\s*Chat\s*(-?\d+)\s*\((.+)\)",
    re.IGNORECASE | re.DOTALL
)


async def ensure_text_column(conn):
    """Ensure the title column is TEXT type (not VARCHAR)."""
    try:
        check = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='truck_groups' AND column_name='title'
        """)
        if check and "character" in check:
            logger.warning("⚠️ Column 'title' is VARCHAR — expanding to TEXT...")
            await conn.execute("ALTER TABLE truck_groups ALTER COLUMN title TYPE TEXT;")
            logger.info("✅ Column 'title' converted to TEXT successfully.")
    except Exception as e:
        logger.error(f"Failed to verify/alter column type: {e}")


async def insert_record(conn, unit: str, chat_id: int, title: str):
    """Insert or update record directly with 'active' flag."""
    try:
        await conn.execute(
            """
            INSERT INTO truck_groups (unit, chat_id, title, created_at, active)
            VALUES ($1, $2, $3, NOW(), TRUE)
            ON CONFLICT (unit) DO UPDATE
            SET chat_id = EXCLUDED.chat_id,
                title = EXCLUDED.title,
                active = TRUE,
                created_at = NOW();
            """,
            unit, chat_id, title
        )
        logger.info(f"✅ Inserted {unit} → {chat_id} ({title})")
    except Exception as e:
        logger.error(f"💥 Insert failed for {unit}: {e}")


async def import_from_logs(file_path: str = "./scripts/logs.json"):
    """Parse logs.json and rebuild DB from it."""
    pool = await init_pool()
    imported, skipped = 0, 0

    # Load and decode file safely
    with open(file_path, "r", encoding="utf-8") as f:
        logs = json.load(f)

    async with pool.acquire() as conn:
        await ensure_text_column(conn)

        for entry in logs:
            msg = entry.get("message", "").replace("\u001b", "").replace("\x1b", "")
            match = LINK_RE.search(msg)
            if not match:
                skipped += 1
                continue

            unit, chat_id, title = match.groups()
            try:
                chat_id = int(chat_id)
            except ValueError:
                skipped += 1
                continue

            # Normalize text (keep emojis, full names, phones)
            title = title.encode("utf-8", "ignore").decode().strip()
            await insert_record(conn, unit.strip(), chat_id, title)
            imported += 1

    logger.info(f"🎯 Import complete → Added: {imported}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(import_from_logs())
