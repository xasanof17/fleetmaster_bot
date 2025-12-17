"""
services/email_verification_service.py
FleetMaster — Gmail Verification Logic
"""

import random
import string
from datetime import datetime

from services.user_service import get_user_by_id, mark_gmail_verified, set_verification_code
from utils.logger import get_logger

logger = get_logger(__name__)

RESEND_COOLDOWN = 60  # seconds
MAX_ATTEMPTS = 5


async def create_or_resend_code(user_id: int, gmail: str) -> str | None:
    """Generates a 6-digit code and saves it to the user record."""
    user = await get_user_by_id(user_id)
    now = datetime.now()

    # Cooldown Check
    if user and user.get("last_code_sent_at"):
        delta = now.timestamp() - user["last_code_sent_at"].timestamp()
        if delta < RESEND_COOLDOWN:
            logger.warning(f"User {user_id} requested code too soon.")
            return None

    # Generate 6 digits
    code = "".join(random.choices(string.digits, k=6))

    # Save to bot_users table
    await set_verification_code(user_id, code)
    return code


async def verify_code(user_id: int, input_code: str) -> bool:
    """Checks if the code matches and marks user as verified."""
    user = await get_user_by_id(user_id)

    if not user or not user.get("verification_code"):
        return False

    # Check match
    if user["verification_code"] == input_code:
        await mark_gmail_verified(user_id)
        return True

    return False
