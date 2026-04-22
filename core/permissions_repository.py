"""
Webapp permissions repository — data access layer for permissions.
"""
import logging
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions_model import WebappPermission

logger = logging.getLogger(__name__)


class PermissionRepository:
    """Data access layer for webapp permissions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant(self, username: str, webapp_id: str) -> Optional[WebappPermission]:
        """
        Grant access to a webapp for a user.
        
        Args:
            username: Username to grant access to
            webapp_id: App identifier (e.g., 'example_app')
            
        Returns:
            Created permission record, or None if duplicate
            
        Raises:
            Exception: If database error occurs (non-duplicate)
        """
        try:
            # Check if permission already exists
            existing = await self.get(username, webapp_id)
            if existing:
                logger.debug(f"Permission already exists for {username} → {webapp_id}")
                return existing

            # Create new permission
            perm = WebappPermission(username=username, webapp_id=webapp_id)
            self.db.add(perm)
            await self.db.flush()
            await self.db.refresh(perm)
            logger.info(f"Granted permission: {username} → {webapp_id}")
            return perm
        except IntegrityError as e:
            logger.debug(f"Integrity error (likely duplicate): {e}")
            await self.db.rollback()
            # Try to retrieve the existing record
            return await self.get(username, webapp_id)

    async def revoke(self, username: str, webapp_id: str) -> bool:
        """
        Revoke access to a webapp for a user.
        
        Args:
            username: Username to revoke access from
            webapp_id: App identifier
            
        Returns:
            True if revoked, False if permission didn't exist
        """
        result = await self.db.execute(
            delete(WebappPermission).where(
                (WebappPermission.username == username) &
                (WebappPermission.webapp_id == webapp_id)
            )
        )
        affected = result.rowcount
        if affected > 0:
            logger.info(f"Revoked permission: {username} → {webapp_id}")
            return True
        else:
            logger.debug(f"No permission to revoke for {username} → {webapp_id}")
            return False

    async def get(self, username: str, webapp_id: str) -> Optional[WebappPermission]:
        """Get a specific permission record."""
        result = await self.db.execute(
            select(WebappPermission).where(
                (WebappPermission.username == username) &
                (WebappPermission.webapp_id == webapp_id)
            )
        )
        return result.scalars().first()

    async def has_permission(self, username: str, webapp_id: str) -> bool:
        """Check if user has access to a webapp."""
        perm = await self.get(username, webapp_id)
        return perm is not None

    async def list_user_webapps(self, username: str) -> list[WebappPermission]:
        """List all webapps a user has access to."""
        result = await self.db.execute(
            select(WebappPermission).where(WebappPermission.username == username)
        )
        return result.scalars().all()

    async def list_webapp_users(self, webapp_id: str) -> list[WebappPermission]:
        """List all users with access to a webapp."""
        result = await self.db.execute(
            select(WebappPermission).where(WebappPermission.webapp_id == webapp_id)
        )
        return result.scalars().all()

    async def revoke_all_webapp_access(self, username: str) -> int:
        """Revoke all webapp access for a user (e.g., when user is deleted)."""
        result = await self.db.execute(
            delete(WebappPermission).where(WebappPermission.username == username)
        )
        count = result.rowcount
        if count > 0:
            logger.info(f"Revoked all webapp access for {username}")
        return count
