"""
FleetMaster Bot - User Access & Role Management
Improved JSON-based version (safe, consistent, admin-ready)
"""

import json
from dataclasses import dataclass, asdict, field
from enum import StrEnum
from pathlib import Path
from typing import Optional
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


# ======================================================
# ENUMS
# ======================================================


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


# ======================================================
# DATACLASS
# ======================================================


@dataclass
class AccessRequest:
    tg_id: int
    telegram_username: Optional[str]
    full_name: str
    gmail: str
    phone: str
    role: str
    status: AccessStatus
    # default_factory bo'lmasa import paytida bitta vaqt hamma uchun yoziladi
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    approved_by: Optional[int] = None


# ======================================================
# STORAGE CORE
# ======================================================


class AccessStorage:
    def __init__(self, base_dir: str = "data/users"):
        self.base_dir = Path(base_dir)
        self.pending = self.base_dir / "pending"
        self.approved = self.base_dir / "approved"
        self.denied = self.base_dir / "denied"
        self.deleted = self.base_dir / "deleted"

        for d in (self.base_dir, self.pending, self.approved, self.denied, self.deleted):
            d.mkdir(parents=True, exist_ok=True)

    # -------------------------------
    # Internal helpers
    # -------------------------------

    def _path(self, tg_id: int, status: AccessStatus) -> Path:
        mapping = {
            AccessStatus.PENDING: self.pending,
            AccessStatus.APPROVED: self.approved,
            AccessStatus.DENIED: self.denied,
            AccessStatus.DELETED: self.deleted,
        }
        return mapping[status] / f"{tg_id}.json"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Safe write to avoid corrupt JSON."""
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            tmp.replace(path)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to write file %s: %s", path, e)

    def _load_file(self, path: Path) -> Optional[AccessRequest]:
        """Single file loader + status normalization."""
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
        except Exception as e:  # noqa: BLE001
            logger.error("❌ Corrupted JSON in %s: %s", path, e)
            return None

        # status ni har doim AccessStatus ga o'giramiz
        raw_status = data.get("status", AccessStatus.PENDING)
        if isinstance(raw_status, AccessStatus):
            norm_status = raw_status
        else:
            try:
                norm_status = AccessStatus(str(raw_status))
            except Exception:
                logger.warning(
                    "Unknown status '%s' in %s, falling back to PENDING", raw_status, path
                )
                norm_status = AccessStatus.PENDING

        data["status"] = norm_status

        try:
            return AccessRequest(**data)
        except Exception as e:  # noqa: BLE001
            logger.error("❌ Failed to build AccessRequest from %s: %s", path, e)
            return None

    def _load_any(self, tg_id: int) -> Optional[AccessRequest]:
        for status in AccessStatus:
            path = self._path(tg_id, status)
            req = self._load_file(path)
            if req:
                return req
        return None

    # -------------------------------
    # Public API
    # -------------------------------

    def get(self, tg_id: int) -> Optional[AccessRequest]:
        return self._load_any(tg_id)

    def save_pending(self, req: AccessRequest) -> None:
        self.delete_user(req.tg_id)
        req.status = AccessStatus.PENDING
        path = self._path(req.tg_id, AccessStatus.PENDING)
        self._atomic_write(path, asdict(req))

    def update_status(
        self, tg_id: int, new_status: AccessStatus, approved_by: int | None = None
    ) -> Optional[AccessRequest]:
        req = self.get(tg_id)
        if not req:
            return None

        self.delete_user(tg_id)

        req.status = new_status
        req.approved_by = approved_by

        path = self._path(req.tg_id, new_status)
        self._atomic_write(path, asdict(req))
        return req

    def update_role(self, tg_id: int, new_role: str) -> Optional[AccessRequest]:
        req = self.get(tg_id)
        if not req:
            return None

        req.role = new_role
        path = self._path(req.tg_id, req.status)
        self._atomic_write(path, asdict(req))
        return req

    def delete_user(self, tg_id: int) -> None:
        """Remove user files from all status folders."""
        for status in AccessStatus:
            path = self._path(tg_id, status)
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:  # noqa: BLE001
                    logger.error("Failed to delete %s: %s", path, e)

    def has_access(self, tg_id: int) -> bool:
        req = self.get(tg_id)
        # bu yerda == ishlatyapmiz, enum va string mismatch bo'lmasligi uchun yuqorida normalize qildik
        return bool(req and req.status == AccessStatus.APPROVED)

    # -------------------------------
    # Admin helper functions
    # -------------------------------

    def _list_in_dir(self, directory: Path) -> list[AccessRequest]:
        users: list[AccessRequest] = []
        for file in directory.glob("*.json"):
            req = self._load_file(file)
            if req:
                users.append(req)
        return users

    def list_pending(self) -> list[AccessRequest]:
        return self._list_in_dir(self.pending)

    def list_approved(self) -> list[AccessRequest]:
        return self._list_in_dir(self.approved)

    def list_denied(self) -> list[AccessRequest]:
        return self._list_in_dir(self.denied)

    def list_deleted(self) -> list[AccessRequest]:
        return self._list_in_dir(self.deleted)


# Singleton instance
access_storage = AccessStorage()
