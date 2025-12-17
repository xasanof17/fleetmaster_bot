"""
services/user_service.py
FleetMaster — User Authentication & Authorization Layer
SAFE • MODERN • PRODUCTION READY
"""

from __future__ import annotations

from config.db import get_pool
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Only log INFO in production
_LOG_INFO_ENABLED = str(getattr(settings, "ENV", "")).lower() in {"prod", "production"}


def _info(msg: str):
    if _LOG_INFO_ENABLED:
        logger.info(msg)


def _error(msg: str):
    logger.error(msg)


_TABLE_READY = False


# ============================================================
# TABLE SETUP
# ============================================================
async def ensure_user_table():
    """Create bot_users table safely with all required fields."""
    global _TABLE_READY
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS public.bot_users (
                user_id BIGINT PRIMARY KEY,       -- Telegram User ID
                full_name TEXT NOT NULL,
                nickname TEXT,                    -- Telegram @username
                role TEXT,                        -- DISPATCHER, MANAGER, ADMIN
                phone_number TEXT,
                gmail TEXT UNIQUE,
                is_verified BOOLEAN DEFAULT FALSE, -- Gmail verification code status
                is_approved BOOLEAN DEFAULT FALSE, -- Admin manual approval status
                active BOOLEAN DEFAULT TRUE,       -- Toggle for firing/removing users
                verification_code TEXT,            -- Latest 6-digit code
                last_code_sent_at TIMESTAMPTZ,     -- For Resend Cooldown
                verify_attempts INT DEFAULT 0,     -- Anti-bruteforce
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                last_active_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    if not _TABLE_READY:
        _info("DB ready: bot_users")
        _TABLE_READY = True


# ============================================================
# USER ACTIONS
# ============================================================


async def get_user_by_id(user_id: int) -> dict | None:
    """Fetch user profile and status."""
    await ensure_user_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bot_users WHERE user_id=$1", user_id)
        return dict(row) if row else None


async def save_signup_data(data: dict):
    """
    Step 1: Save the 5 pillars of user information.
    Sets is_verified=FALSE and is_approved=FALSE initially.
    """
    await ensure_user_table()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_users
            (user_id, full_name, nickname, role, phone_number, gmail, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                nickname = EXCLUDED.nickname,
                role = EXCLUDED.role,
                phone_number = EXCLUDED.phone_number,
                gmail = EXCLUDED.gmail,
                updated_at = NOW();
        """,
            data["user_id"],
            data["full_name"],
            data["nickname"],
            data["role"],
            data["phone_number"],
            data["gmail"],
        )


async def set_verification_code(user_id: int, code: str):
    """Saves the code and updates the sent timestamp for cooldown checks."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE bot_users
            SET verification_code = $2,
                last_code_sent_at = NOW(),
                verify_attempts = 0,
                updated_at = NOW()
            WHERE user_id = $1
        """,
            user_id,
            code,
        )


async def mark_gmail_verified(user_id: int):
    """Updates status after user enters correct code."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE bot_users
            SET is_verified = TRUE,
                verification_code = NULL,
                updated_at = NOW()
            WHERE user_id = $1
        """,
            user_id,
        )


async def approve_user(user_id: int):
    """Step 2: Admin final approval from the notification panel."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE bot_users SET is_approved=TRUE, updated_at=NOW() WHERE user_id=$1", user_id
        )


async def update_last_active(user_id: int):
    """Ping whenever the user performs an action."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE bot_users SET last_active_at=NOW() WHERE user_id=$1", user_id)
