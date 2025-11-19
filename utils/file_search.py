import os

FILES_BASE = "files"

DOC_FOLDERS = {
    "registrations_2026": "registrations_2026",
    "new_mexico": "new_mexico",
    "lease": "lease_agreements",
    "inspection_2025": "annual_inspection",
}


def find_truck_document(truck_number: str, doc_type: str) -> str | None:
    """
    Find the first document file in the given doc_type folder
    that starts with the given truck_number.
    """
    folder = DOC_FOLDERS.get(doc_type)
    if not folder:
        return None

    folder_path = os.path.join(FILES_BASE, folder)
    if not os.path.exists(folder_path):
        return None

    for f in os.listdir(folder_path):
        if f.lower().startswith(truck_number.lower()):
            return os.path.join(folder_path, f)

    return None
