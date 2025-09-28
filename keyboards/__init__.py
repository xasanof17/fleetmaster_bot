# keyboards/__init__.py
from .main_menu import get_main_menu_keyboard, get_help_keyboard
from .pm_trucker import (
    get_pm_trucker_menu,
    get_vehicles_list_keyboard,
    get_vehicle_details_keyboard,
    get_back_to_pm_keyboard,
    get_search_options_keyboard,
    get_search_results_keyboard,
)
from .pm_services import (get_pm_services_menu, get_pm_vehicles_keyboard, get_pm_vehicle_details_keyboard)
from .documents import documents_menu_kb

__all__ = [
    "get_main_menu_keyboard",
    "get_help_keyboard",
    "get_pm_trucker_menu",
    "get_vehicles_list_keyboard",
    "get_vehicle_details_keyboard",
    "get_back_to_pm_keyboard",
    "get_search_options_keyboard",
    "get_search_results_keyboard",
    "documents_menu_kb",
    "get_pm_services_menu",
    "get_pm_vehicles_keyboard",
    "get_pm_vehicle_details_keyboard",
]
