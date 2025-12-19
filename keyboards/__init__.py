# keyboards/__init__.py

from .documents import documents_menu_kb
from .main_menu import get_help_keyboard, get_main_menu_keyboard
from .manage_users import manage_users_menu, user_action_kb
from .pm_services import (
    get_calendar_keyboard,
    get_pm_search_keyboard,
    get_pm_services_menu,
    get_pm_vehicle_details_keyboard,
    get_pm_vehicles_keyboard,
    get_time_picker_keyboard,
    urgent_oil_list_keyboard,
)
from .pm_trucker import (
    get_back_to_pm_keyboard,
    get_pm_trucker_menu,
    get_search_options_keyboard,
    get_search_results_keyboard,
    get_vehicle_details_keyboard,
    get_vehicles_list_keyboard,
)
from .trailer import trailer_file_kb, trailer_menu_kb

__all__ = [
    # main menu
    "get_main_menu_keyboard",
    "get_help_keyboard",
    # pm trucker
    "get_pm_trucker_menu",
    "get_vehicles_list_keyboard",
    "get_vehicle_details_keyboard",
    "get_back_to_pm_keyboard",
    "get_search_options_keyboard",
    "get_search_results_keyboard",
    # documents
    "documents_menu_kb",
    # pm services
    "get_pm_services_menu",
    "get_pm_search_keyboard",
    "get_pm_vehicles_keyboard",
    "get_pm_vehicle_details_keyboard",
    "urgent_oil_list_keyboard",
    "get_calendar_keyboard",
    "get_time_picker_keyboard",
    # trailer
    "trailer_menu_kb",
    "trailer_file_kb",
    # manage users
    "manage_users_menu",
    "user_action_kb",
]
