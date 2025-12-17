"""
utils/mailer.py
FleetMaster — Email Dispatcher
"""

import smtplib
from email.message import EmailMessage

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


async def send_verification_email(to_email: str, code: str):
    """
    Sends a 6-digit verification code to the user's Gmail.
    Requires SMTP_USER and SMTP_PASSWORD in your .env
    """
    msg = EmailMessage()
    msg.set_content(
        f"Welcome to FleetMaster!\n\n"
        f"Your verification code is: {code}\n"
        f"This code will expire in 10 minutes.\n\n"
        f"If you did not request this, please ignore this email."
    )

    msg["Subject"] = f"FleetMaster Verification Code: {code}"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email

    try:
        # Use a synchronous executor or run_in_executor for production
        # For simplicity, we use standard smtplib here
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"✅ Verification email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {e}")
        return False
