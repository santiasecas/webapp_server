"""
Admin App — Platform Administration
=====================================
Provides admin-only endpoints for:
  - User and group overview
  - Webapp permission management (grant / revoke)
  - Permission matrix UI

Only users in the 'admins' group can access this app.
"""
from fastapi import FastAPI

from core.registry import AppRegistry

admin_app = FastAPI(title="Admin — Platform Administration")

from apps.admin_app.routers import permissions as perm_router   # noqa: E402
from apps.admin_app.routers import users as users_router         # noqa: E402

admin_app.include_router(perm_router.router)
admin_app.include_router(users_router.router)

AppRegistry.register(
    name="admin_app",
    router=admin_app,
    prefix="/admin",
    description="Platform administration — users, groups and permissions",
    icon="🛡",
    category="Administration",
    visible=True,
    permission_required=False,  # Controlled by require_group("admins") in routes
)

app_module = admin_app
