"""
Webapp permissions service — business logic for permission management.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions_repository import PermissionRepository
from core.registry import AppRegistry
from core.users import UserStore

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    """Base permission error."""
    pass


class UserNotFoundError(PermissionError):
    """User does not exist."""
    pass


class WebappNotFoundError(PermissionError):
    """Webapp does not exist."""
    pass


class PermissionService:
    """Business logic for managing webapp permissions."""

    def __init__(self, db: AsyncSession, user_store: UserStore):
        self.repo = PermissionRepository(db)
        self.user_store = user_store

    async def grant_access(self, username: str, webapp_id: str) -> dict:
        """
        Grant a user access to a webapp.
        
        Args:
            username: Target user
            webapp_id: Target webapp
            
        Returns:
            Success response dict
            
        Raises:
            UserNotFoundError: User doesn't exist
            WebappNotFoundError: Webapp doesn't exist
        """
        # Validate user exists
        user = self.user_store.get(username)
        if not user:
            raise UserNotFoundError(f"User '{username}' not found")

        # Validate webapp exists
        if webapp_id not in AppRegistry.apps:
            raise WebappNotFoundError(f"Webapp '{webapp_id}' not found")

        # Grant permission
        perm = await self.repo.grant(username, webapp_id)
        return {
            "success": True,
            "message": f"Access granted to {username} for {webapp_id}",
            "username": username,
            "webapp_id": webapp_id,
        }

    async def revoke_access(self, username: str, webapp_id: str) -> dict:
        """
        Revoke a user's access to a webapp.
        
        Args:
            username: Target user
            webapp_id: Target webapp
            
        Returns:
            Success response dict
            
        Raises:
            UserNotFoundError: User doesn't exist
            WebappNotFoundError: Webapp doesn't exist
        """
        # Validate user exists
        user = self.user_store.get(username)
        if not user:
            raise UserNotFoundError(f"User '{username}' not found")

        # Validate webapp exists
        if webapp_id not in AppRegistry.apps:
            raise WebappNotFoundError(f"Webapp '{webapp_id}' not found")

        # Revoke permission
        revoked = await self.repo.revoke(username, webapp_id)
        
        return {
            "success": True,
            "message": f"Access revoked for {username} from {webapp_id}",
            "username": username,
            "webapp_id": webapp_id,
            "was_granted": revoked,
        }

    async def check_access(self, username: str, webapp_id: str, user_groups: list[str]) -> bool:
        """
        Check if a user has access to a webapp.
        
        Rules:
        1. Admins (group 'admins') have access to all webapps
        2. Other users need explicit permission in the table
        
        Args:
            username: User to check
            webapp_id: Webapp to check access to
            user_groups: List of groups the user belongs to
            
        Returns:
            True if user has access, False otherwise
        """
        # Admins always have access
        if "admins" in user_groups:
            return True

        # Check explicit permission
        has_perm = await self.repo.has_permission(username, webapp_id)
        return has_perm

    async def list_user_webapps(self, username: str, user_groups: list[str]) -> list[dict]:
        """
        List all webapps a user has access to.
        
        Returns:
            List of webapp info dicts
        """
        accessible_webapps = []

        # If admin, all webapps are accessible
        if "admins" in user_groups:
            for webapp_id, app_info in AppRegistry.apps.items():
                accessible_webapps.append({
                    "id": webapp_id,
                    "name": app_info["name"],
                    "prefix": app_info["prefix"],
                    "description": app_info["description"],
                    "icon": app_info["icon"],
                    "access_type": "admin",
                })
            return accessible_webapps

        # Otherwise, only explicitly granted webapps
        perms = await self.repo.list_user_webapps(username)
        for perm in perms:
            if perm.webapp_id in AppRegistry.apps:
                app_info = AppRegistry.apps[perm.webapp_id]
                accessible_webapps.append({
                    "id": perm.webapp_id,
                    "name": app_info["name"],
                    "prefix": app_info["prefix"],
                    "description": app_info["description"],
                    "icon": app_info["icon"],
                    "access_type": "explicit",
                })

        return accessible_webapps
