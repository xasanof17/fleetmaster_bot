# from aiogram import Router, types, F
# from utils import location_logger
# from config import settings

# router = Router()

# # List of admin user IDs (Telegram)
# ADMINS = settings.ADMINS  # e.g., [123456789, 987654321]

# @router.message(F.text == "/locationlogs")
# async def cmd_location_logs(message: types.Message):
#     if message.from_user.id not in ADMINS:
#         await message.answer("❌ You are not authorized to view logs.")
#         return

#     logs = location_logger.read_logs(limit=15)
#     if not logs:
#         await message.answer("📂 No location requests logged yet.")
#         return

#     text = "📊 **Recent Location Requests**\n\n"
#     for log in logs:
#         text += (
#             f"👤 User: `{log['user_id']}`\n"
#             f"🚛 Vehicle: `{log['vehicle_id']}`\n"
#             f"📍 Type: {log['location_type']}\n"
#             f"🏠 Address: {log.get('address', 'N/A')}\n"
#             f"🕒 {log['timestamp']}\n\n"
#         )

#     await message.answer(text, parse_mode="Markdown")
