"""
FleetMaster Bot - User Access & Role Management
Temporary JSON storage version
"""

import json
from dataclasses import dataclass, asdict
from enum import StrEnum
from pathlib import Path
from typing import Optional
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


class AccessStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    DELETED = "deleted"


class UserRole(StrEnum):
    MANAGER = "Manager"
    DISPATCHER = "Dispatcher"
    FLEET_SPEC = "Fleet specialist"
    SAFETY_SPEC = "Safety specialist"
    UPDATER = "Updater"
    FUEL_COORD = "Fuel coordinator"
    TRAILER_COORD = "Trailer coordinator"


@dataclass
class AccessRequest:
    tg_id: int
    telegram_username: Optional[str]
    full_name: str
    gmail: str
    phone: str
    role: str
    status: AccessStatus
    created_at: str = datetime.now().strftime("%Y-%m-%d")
    approved_by: Optional[int] = None


class AccessStorage:
    def __init__(self, base_dir="data/users"):
        self.base_dir = Path(base_dir)
        self.pending = self.base_dir / "pending"
        self.approved = self.base_dir / "approved"
        self.denied = self.base_dir / "denied"
        self.deleted = self.base_dir / "deleted"

        for d in (self.base_dir, self.pending, self.approved, self.denied, self.deleted):
            d.mkdir(parents=True, exist_ok=True)

    def _path(self, tg_id: int, status: AccessStatus):
        mapping = {
            AccessStatus.PENDING: self.pending,
            AccessStatus.APPROVED: self.approved,
            AccessStatus.DENIED: self.denied,
            AccessStatus.DELETED: self.deleted,
        }
        return mapping[status] / f"{tg_id}.json"

    def _load_any(self, tg_id: int) -> Optional[AccessRequest]:
        for status in AccessStatus:
            path = self._path(tg_id, status)
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    return AccessRequest(**data)
                except Exception as e:
                    logger.error(f"Failed to load user {tg_id}: {e}")
        return None

    def get(self, tg_id: int):
        return self._load_any(tg_id)

    def save_pending(self, req: AccessRequest):
        self.delete_user(req.tg_id)
        path = self._path(req.tg_id, AccessStatus.PENDING)
        req.status = AccessStatus.PENDING
        path.write_text(json.dumps(asdict(req), ensure_ascii=False, indent=2))

    def update_status(self, tg_id: int, new_status: AccessStatus, approved_by=None):
        req = self.get(tg_id)
        if not req:
            return None
        self.delete_user(tg_id)
        req.status = new_status
        req.approved_by = approved_by
        path = self._path(tg_id, new_status)
        path.write_text(json.dumps(asdict(req), ensure_ascii=False, indent=2))
        return req

    def update_role(self, tg_id: int, new_role: str):
        req = self.get(tg_id)
        if not req:
            return None
        req.role = new_role
        path = self._path(req.tg_id, req.status)
        path.write_text(json.dumps(asdict(req), ensure_ascii=False, indent=2))
        return req

    def delete_user(self, tg_id: int):
        for status in AccessStatus:
            path = self._path(tg_id, status)
            if path.exists():
                path.unlink()

    def has_access(self, tg_id: int):
        req = self.get(tg_id)
        return bool(req and req.status == AccessStatus.APPROVED)


access_storage = AccessStorage()
