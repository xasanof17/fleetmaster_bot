"""
utils/mailer.py
FleetMaster — Email Dispatcher (Resend via HTTP)
ASYNC • CLOUD SAFE • PRODUCTION READY
"""

import httpx

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = settings.RESEND_API_KEY
EMAIL_FROM = settings.EMAIL_FROM


def build_verification_template(code: str) -> str:
    """Simple, modern verification email template"""
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
</head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Inter,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 0;">
        <table width="420" style="background:#ffffff;border-radius:12px;padding:32px;">
          <tr>
            <td align="center">
              <h2 style="margin:0;color:#111827;">🚛 FleetMaster</h2>
              <p style="color:#6b7280;margin:8px 0 24px;">
                Email verification
              </p>

              <div style="
                background:#f3f4f6;
                border-radius:10px;
                padding:16px 24px;
                margin-bottom:24px;
              ">
                <span style="
                  font-size:28px;
                  font-weight:700;
                  letter-spacing:4px;
                  color:#111827;
                ">
                  {code}
                </span>
              </div>

              <p style="font-size:14px;color:#374151;margin-bottom:12px;">
                This code expires in <strong>10 minutes</strong>.
              </p>

              <p style="font-size:12px;color:#9ca3af;">
                If you didn’t request this, you can ignore this email.
              </p>
            </td>
          </tr>
        </table>

        <p style="margin-top:16px;font-size:12px;color:#9ca3af;">
          © FleetMaster
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""


async def send_verification_email(to_email: str, code: str) -> bool:
    if not settings.RESEND_API_KEY:
        logger.error("❌ RESEND_API_KEY is missing")
        return False

    payload = {
        "from": settings.EMAIL_FROM or "FleetMaster <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"Your FleetMaster verification code: {code}",
        "html": build_verification_template(code),
    }

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                RESEND_API_URL,
                headers=headers,
                json=payload,
            )

        if response.status_code not in (200, 201):
            logger.error(f"❌ Resend error {response.status_code}: {response.text}")
            return False

        logger.info(f"✅ Verification email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"❌ Email send failed: {e}")
        return False
