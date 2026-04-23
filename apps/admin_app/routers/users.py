"""
apps/admin_app/routers/users.py — User and group overview for admins.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from core.auth import UserSession, require_group
from core.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Admin – Users"])

AdminOnly = Annotated[UserSession, Depends(require_group("admins"))]


@router.get("/", response_class=HTMLResponse, name="admin:index")
async def admin_index(request: Request, session: AdminOnly):
    """Admin dashboard — overview of users, groups and apps."""
    from core.registry import AppRegistry
    from core.users import get_user_store

    store = get_user_store()
    all_users = store.all_users()
    all_groups = store.all_groups()
    all_apps = AppRegistry.get_app_list()

    # Apps that require explicit permissions
    restricted_apps = [a for a in all_apps if a.get("permission_required")]

    return templates.TemplateResponse(
        "admin_app/index.html",
        {
            "request": request,
            "session": session,
            "title": "Administration",
            "users": all_users,
            "groups": all_groups,
            "all_apps": all_apps,
            "restricted_apps": restricted_apps,
            "stats": {
                "total_users": len(all_users),
                "active_users": sum(1 for u in all_users if u.active),
                "total_groups": len(all_groups),
                "total_apps": len(all_apps),
                "restricted_apps": len(restricted_apps),
            },
        },
    )


@router.get("/users", response_class=HTMLResponse, name="admin:users_list")
async def admin_users_list(request: Request, session: AdminOnly):
    """List all users with their groups."""
    from core.users import get_user_store
    store = get_user_store()
    users = store.all_users()
    return templates.TemplateResponse(
        "admin_app/users.html",
        {
            "request": request,
            "session": session,
            "title": "Users",
            "users": users,
        },
    )
