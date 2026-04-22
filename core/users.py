"""
core/users.py — User store with groups/roles.

File format (.users.json):
{
  "users": {
    "admin": {
      "password_hash": "$2y$12$...",
      "groups": ["admins", "users"],
      "display_name": "Administrator",
      "active": true
    },
    "alice": {
      "password_hash": "$2y$12$...",
      "groups": ["users"],
      "display_name": "Alice",
      "active": true
    }
  }
}

Groups are free-form strings. Built-in conventions:
  "admins"  — full platform access
  "users"   — standard read/write access
  "viewers" — read-only access

Hot-reload: file is re-read when mtime changes, no restart needed.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.auth_passwords import verify_password, hash_password_bcrypt

logger = logging.getLogger(__name__)


@dataclass
class UserRecord:
    username: str
    password_hash: str
    groups: list[str] = field(default_factory=list)
    display_name: str = ""
    active: bool = True

    def has_group(self, group: str) -> bool:
        return group in self.groups

    def has_any_group(self, *groups: str) -> bool:
        return any(g in self.groups for g in groups)

    def has_all_groups(self, *groups: str) -> bool:
        return all(g in self.groups for g in groups)

    @property
    def primary_group(self) -> str:
        """Returns the first (most privileged) group, or 'users' as fallback."""
        return self.groups[0] if self.groups else "users"

    def verify_password(self, password: str) -> bool:
        if not self.active:
            return False
        return verify_password(password, self.password_hash)


class UserStore:
    """
    Reads and caches the .users.json file.
    Automatically reloads when the file changes (hot-reload).
    Thread-safe for reads (GIL + immutable replace pattern).
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self._users: dict[str, UserRecord] = {}
        self._mtime: float = 0.0
        self._load()

    def _load(self) -> None:
        if not self.filepath.exists():
            if self._users:  # Only warn once
                logger.warning(f"Users file not found: {self.filepath}")
            self._users = {}
            return

        try:
            mtime = self.filepath.stat().st_mtime
            if mtime == self._mtime:
                return  # No changes

            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            users: dict[str, UserRecord] = {}
            for username, info in data.get("users", {}).items():
                if not isinstance(info, dict):
                    logger.warning(f"Skipping malformed user entry: {username!r}")
                    continue
                users[username] = UserRecord(
                    username=username,
                    password_hash=info.get("password_hash", ""),
                    groups=info.get("groups", ["users"]),
                    display_name=info.get("display_name", username),
                    active=info.get("active", True),
                )

            self._users = users
            self._mtime = mtime
            logger.info(
                f"Loaded {len(users)} user(s) from {self.filepath} "
                f"[groups: {sorted({g for u in users.values() for g in u.groups})}]"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.filepath}: {e}")
        except Exception as e:
            logger.error(f"Error loading users file: {e}")

    def _ensure_fresh(self) -> None:
        """Check mtime and reload if needed."""
        if not self.filepath.exists():
            self._users = {}
            return
        try:
            if self.filepath.stat().st_mtime != self._mtime:
                self._load()
        except OSError:
            pass

    def get(self, username: str) -> Optional[UserRecord]:
        self._ensure_fresh()
        return self._users.get(username)

    def verify(self, username: str, password: str) -> Optional[UserRecord]:
        """Returns the UserRecord on success, None on failure."""
        self._ensure_fresh()
        user = self._users.get(username)
        if user is None:
            return None
        if user.verify_password(password):
            return user
        return None

    def all_users(self) -> list[UserRecord]:
        self._ensure_fresh()
        return list(self._users.values())

    def users_in_group(self, group: str) -> list[UserRecord]:
        self._ensure_fresh()
        return [u for u in self._users.values() if u.has_group(group)]

    def all_groups(self) -> list[str]:
        self._ensure_fresh()
        groups: set[str] = set()
        for u in self._users.values():
            groups.update(u.groups)
        return sorted(groups)

    def save(self, filepath: Optional[str] = None) -> None:
        """Persist current state back to JSON."""
        path = Path(filepath) if filepath else self.filepath
        data = {
            "users": {
                u.username: {
                    "password_hash": u.password_hash,
                    "groups": u.groups,
                    "display_name": u.display_name,
                    "active": u.active,
                }
                for u in self._users.values()
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Reset mtime so next read detects our own write
        self._mtime = path.stat().st_mtime
        logger.info(f"Saved {len(self._users)} user(s) to {path}")

    def add_or_update_user(
        self,
        username: str,
        password: str,
        groups: list[str],
        display_name: str = "",
        active: bool = True,
    ) -> UserRecord:
        self._ensure_fresh()
        record = UserRecord(
            username=username,
            password_hash=hash_password_bcrypt(password),
            groups=groups,
            display_name=display_name or username,
            active=active,
        )
        self._users[username] = record
        return record

    def delete_user(self, username: str) -> bool:
        self._ensure_fresh()
        if username in self._users:
            del self._users[username]
            return True
        return False

    def set_password(self, username: str, password: str) -> bool:
        self._ensure_fresh()
        user = self._users.get(username)
        if user is None:
            return False
        user.password_hash = hash_password_bcrypt(password)
        return True

    def set_groups(self, username: str, groups: list[str]) -> bool:
        self._ensure_fresh()
        user = self._users.get(username)
        if user is None:
            return False
        user.groups = groups
        return True


# ── Module-level singleton ────────────────────────────────────────────────────
# Initialized lazily so settings are available at import time.
_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        from core.config import settings
        _store = UserStore(settings.USERS_FILE)
    return _store
