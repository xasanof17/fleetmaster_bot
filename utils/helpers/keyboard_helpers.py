from aiogram.utils.keyboard import InlineKeyboardBuilder


def vehicle_keyboard(vehicle_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="📍 Location", callback_data=f"live_loc:{vehicle_id}")
    return kb.as_markup()


def location_choice_keyboard(vehicle_id: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗺️ Static Location", callback_data=f"loc_static:{vehicle_id}")
    kb.button(text="📡 Live Location", callback_data=f"loc_live:{vehicle_id}")
    return kb.as_markup()


def after_location_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Show Menu", callback_data="show_menu")
    kb.button(text="ℹ️ Show Help", callback_data="show_help")
    return kb.as_markup()
