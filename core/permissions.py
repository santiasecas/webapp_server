"""
core/permissions.py — User-to-webapp permission system.

Table: user_webapp_permissions
  username   — references .users.json username
  webapp_id  — references AppRegistry name (e.g. 'example_app', 'tickets_app')
  granted_by — admin who granted the permission
  created_at — timestamp

Design decisions:
  - Admins (group "admins") ALWAYS have access to all apps — no DB row needed.
  - A webapp can be marked permission_required=True in the registry, which
    activates the permission check.  Apps with permission_required=False are
    accessible to all authenticated users (default behaviour, backward compat).
  - Permissions are checked in middleware so no individual router change needed.
  - Duplicate grants are silently ignored (idempotent).
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, UniqueConstraint, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

logger = logging.getLogger(__name__)


# ── ORM Model ─────────────────────────────────────────────────────────────────

class UserWebappPermission(Base):
    """One row = one user has explicit access to one webapp."""
    __tablename__ = "user_webapp_permissions"
    __table_args__ = (
        UniqueConstraint("username", "webapp_id", name="uq_user_webapp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    webapp_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    granted_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserWebappPermission user={self.username!r} webapp={self.webapp_id!r}>"


# ── Repository ────────────────────────────────────────────────────────────────

class PermissionRepository:
    """Raw DB access — no business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def has_permission(self, username: str, webapp_id: str) -> bool:
        result = await self.db.execute(
            select(UserWebappPermission.id).where(
                UserWebappPermission.username == username,
                UserWebappPermission.webapp_id == webapp_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def grant(
        self, username: str, webapp_id: str, granted_by: str
    ) -> tuple[UserWebappPermission, bool]:
        """
        Grant permission. Returns (record, created).
        created=False means it already existed (idempotent).
        """
        existing = await self.db.execute(
            select(UserWebappPermission).where(
                UserWebappPermission.username == username,
                UserWebappPermission.webapp_id == webapp_id,
            )
        )
        record = existing.scalar_one_or_none()
        if record is not None:
            return record, False

        record = UserWebappPermission(
            username=username,
            webapp_id=webapp_id,
            granted_by=granted_by,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        logger.info(f"Permission granted: user={username!r} webapp={webapp_id!r} by={granted_by!r}")
        return record, True

    async def revoke(self, username: str, webapp_id: str) -> bool:
        """Revoke permission. Returns True if a row was deleted."""
        result = await self.db.execute(
            delete(UserWebappPermission).where(
                UserWebappPermission.username == username,
                UserWebappPermission.webapp_id == webapp_id,
            )
        )
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Permission revoked: user={username!r} webapp={webapp_id!r}")
        return deleted

    async def list_for_user(self, username: str) -> list[UserWebappPermission]:
        result = await self.db.execute(
            select(UserWebappPermission)
            .where(UserWebappPermission.username == username)
            .order_by(UserWebappPermission.webapp_id)
        )
        return list(result.scalars().all())

    async def list_for_webapp(self, webapp_id: str) -> list[UserWebappPermission]:
        result = await self.db.execute(
            select(UserWebappPermission)
            .where(UserWebappPermission.webapp_id == webapp_id)
            .order_by(UserWebappPermission.username)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[UserWebappPermission]:
        result = await self.db.execute(
            select(UserWebappPermission)
            .order_by(UserWebappPermission.webapp_id, UserWebappPermission.username)
        )
        return list(result.scalars().all())

    async def revoke_all_for_user(self, username: str) -> int:
        result = await self.db.execute(
            delete(UserWebappPermission).where(
                UserWebappPermission.username == username,
            )
        )
        return result.rowcount

    async def revoke_all_for_webapp(self, webapp_id: str) -> int:
        result = await self.db.execute(
            delete(UserWebappPermission).where(
                UserWebappPermission.webapp_id == webapp_id,
            )
        )
        return result.rowcount


# ── Service ───────────────────────────────────────────────────────────────────

class PermissionError(Exception):
    """Business-rule violation in permission management."""
    pass


class PermissionService:
    """Business logic for the permission system."""

    def __init__(self, db: AsyncSession):
        self.repo = PermissionRepository(db)

    async def check_access(self, username: str, webapp_id: str) -> bool:
        """
        Returns True if the user can access the webapp.

        Rules (in order):
          1. Admins always have access (checked via session groups — caller's responsibility).
          2. Webapp not marked permission_required → open to all authenticated users.
          3. Otherwise → check user_webapp_permissions table.
        """
        from core.registry import AppRegistry
        app_info = AppRegistry.get_app(webapp_id)
        if app_info is None:
            return False
        if not app_info.get("permission_required", False):
            return True  # Open app — no DB check needed
        return await self.repo.has_permission(username, webapp_id)

    async def grant(
        self,
        username: str,
        webapp_id: str,
        granted_by: str,
    ) -> dict:
        """
        Grant a user access to a webapp.
        Validates both username and webapp_id exist.
        Returns a result dict suitable for JSON responses.
        """
        _validate_user(username)
        _validate_webapp(webapp_id)

        record, created = await self.repo.grant(username, webapp_id, granted_by)
        return {
            "success": True,
            "action": "grant",
            "username": username,
            "webapp_id": webapp_id,
            "created": created,
            "message": (
                f"Permission granted for '{username}' on '{webapp_id}'."
                if created
                else f"'{username}' already had access to '{webapp_id}' (no change)."
            ),
        }

    async def revoke(self, username: str, webapp_id: str) -> dict:
        """
        Revoke a user's access to a webapp.
        Validates both username and webapp_id exist.
        """
        _validate_user(username)
        _validate_webapp(webapp_id)

        deleted = await self.repo.revoke(username, webapp_id)
        return {
            "success": True,
            "action": "revoke",
            "username": username,
            "webapp_id": webapp_id,
            "deleted": deleted,
            "message": (
                f"Access revoked for '{username}' on '{webapp_id}'."
                if deleted
                else f"'{username}' had no access to '{webapp_id}' (no change)."
            ),
        }

    async def list_all(self) -> list[UserWebappPermission]:
        return await self.repo.list_all()

    async def list_for_user(self, username: str) -> list[UserWebappPermission]:
        _validate_user(username)
        return await self.repo.list_for_user(username)

    async def list_for_webapp(self, webapp_id: str) -> list[UserWebappPermission]:
        _validate_webapp(webapp_id)
        return await self.repo.list_for_webapp(webapp_id)

    async def get_matrix(self) -> dict:
        """
        Returns a dict suitable for the admin UI:
        {
          "apps": [{"id": ..., "name": ..., "permission_required": ...}, ...],
          "users": ["alice", "bob", ...],
          "grants": {("alice", "example_app"): True, ...}   # set represented as dict
        }
        """
        from core.registry import AppRegistry
        from core.users import get_user_store

        all_perms = await self.repo.list_all()
        grants: set[tuple[str, str]] = {(p.username, p.webapp_id) for p in all_perms}

        apps = [
            {
                "id": info["name"],
                "label": info["name"].replace("_", " ").title(),
                "icon": info.get("icon", "📦"),
                "permission_required": info.get("permission_required", False),
                "category": info.get("category", ""),
            }
            for info in AppRegistry.apps.values()
            if info.get("visible", True) and info["name"] != "admin_app"
        ]

        store = get_user_store()
        users = [u.username for u in store.all_users() if u.active]

        return {
            "apps": apps,
            "users": users,
            "grants": {f"{u}::{a}": True for (u, a) in grants},
            "raw_grants": list(grants),
        }


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_user(username: str) -> None:
    from core.users import get_user_store
    store = get_user_store()
    if store.get(username) is None:
        raise PermissionError(f"User '{username}' not found.")


def _validate_webapp(webapp_id: str) -> None:
    from core.registry import AppRegistry
    if AppRegistry.get_app(webapp_id) is None:
        raise PermissionError(
            f"Webapp '{webapp_id}' not found. "
            f"Valid IDs: {sorted(AppRegistry.apps.keys())}"
        )


# ── Sync check helper (used by middleware — no DB, in-memory only) ─────────────
# Middleware cannot use async DB easily; it uses a lightweight per-request
# DB call via the async session factory instead.

async def check_webapp_access_db(
    username: str,
    webapp_id: str,
    is_admin: bool,
    db: AsyncSession,
) -> bool:
    """
    Called by middleware. Returns True if access is allowed.
    Fast path: admins always pass. Open apps always pass.
    Only hits the DB for permission_required apps.
    """
    if is_admin:
        return True

    from core.registry import AppRegistry
    app_info = AppRegistry.get_app(webapp_id)
    if app_info is None:
        return False  # Unknown webapp — deny
    if not app_info.get("permission_required", False):
        return True  # Open app

    repo = PermissionRepository(db)
    return await repo.has_permission(username, webapp_id)
