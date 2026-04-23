"""
apps/admin_app/routers/permissions.py

Routes:
  GET  /admin/permissions           — Permission matrix UI (HTML)
  POST /admin/permissions           — Grant or revoke (HTML form, redirect)
  POST /admin/permissions/api       — Grant or revoke (JSON API)
  GET  /admin/permissions/webapp/{webapp_id}  — Permissions for one webapp
  GET  /admin/permissions/user/{username}     — Permissions for one user
"""
import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Path, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import UserSession, require_group
from core.database import get_db
from core.permissions import PermissionError, PermissionService
from core.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/permissions", tags=["Admin – Permissions"])

# Only admins may access any route in this router
AdminOnly = Annotated[UserSession, Depends(require_group("admins"))]


def get_service(db: AsyncSession = Depends(get_db)) -> PermissionService:
    return PermissionService(db)


# ── Pydantic schema for JSON API ──────────────────────────────────────────────

class PermissionRequest(BaseModel):
    usuario_id: str
    webapp_id: str
    accion: Literal["grant", "revoke"]

    @field_validator("usuario_id", "webapp_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


# ── HTML routes ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, name="admin:permissions_matrix")
async def permissions_matrix(
    request: Request,
    session: AdminOnly,
    service: PermissionService = Depends(get_service),
    msg: Optional[str] = None,
    msg_type: Optional[str] = None,
):
    """Permission management matrix — shows all users × all apps."""
    matrix = await service.get_matrix()
    return templates.TemplateResponse(
        "admin_app/permissions.html",
        {
            "request": request,
            "session": session,
            "title": "Permissions",
            "matrix": matrix,
            "msg": msg,
            "msg_type": msg_type or "success",
        },
    )


@router.post("/", response_class=HTMLResponse, name="admin:permissions_submit")
async def permissions_submit(
    request: Request,
    session: AdminOnly,
    service: PermissionService = Depends(get_service),
    username: str = Form(...),
    webapp_id: str = Form(...),
    accion: str = Form(...),
):
    """Handle grant/revoke from the HTML matrix form."""
    try:
        if accion == "grant":
            result = await service.grant(username, webapp_id, granted_by=session.username)
        elif accion == "revoke":
            result = await service.revoke(username, webapp_id)
        else:
            return RedirectResponse(
                url="/admin/permissions/?msg=Invalid+action&msg_type=error",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        msg = result["message"]
        msg_type = "success"
    except PermissionError as exc:
        msg = str(exc)
        msg_type = "error"
    except Exception as exc:
        logger.error(f"Unexpected error in permissions_submit: {exc}")
        msg = "Unexpected error. Check server logs."
        msg_type = "error"

    from urllib.parse import quote
    return RedirectResponse(
        url=f"/admin/permissions/?msg={quote(msg)}&msg_type={msg_type}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── JSON API endpoint (POST /admin/permissions/api) ───────────────────────────

@router.post(
    "/api",
    name="admin:permissions_api",
    summary="Grant or revoke webapp access (JSON)",
    responses={
        200: {"description": "Operation result"},
        400: {"description": "Invalid input"},
        404: {"description": "User or webapp not found"},
        403: {"description": "Not an admin"},
    },
)
async def permissions_api(
    request: Request,
    session: AdminOnly,
    body: PermissionRequest,
    service: PermissionService = Depends(get_service),
):
    """
    JSON endpoint to grant or revoke user access to a webapp.

    Body:
        {
            "usuario_id": "alice",
            "webapp_id": "example_app",
            "accion": "grant"   // or "revoke"
        }

    Returns:
        {
            "success": true,
            "action": "grant",
            "username": "alice",
            "webapp_id": "example_app",
            "message": "Permission granted for 'alice' on 'example_app'."
        }
    """
    try:
        if body.accion == "grant":
            result = await service.grant(
                body.usuario_id, body.webapp_id, granted_by=session.username
            )
        else:
            result = await service.revoke(body.usuario_id, body.webapp_id)

        logger.info(
            f"[API] {body.accion}: user={body.usuario_id!r} "
            f"webapp={body.webapp_id!r} by={session.username!r}"
        )
        return JSONResponse(content=result)

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Unexpected error in permissions_api: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Detail views ──────────────────────────────────────────────────────────────

@router.get(
    "/webapp/{webapp_id}",
    response_class=HTMLResponse,
    name="admin:permissions_by_webapp",
)
async def permissions_by_webapp(
    request: Request,
    session: AdminOnly,
    webapp_id: str = Path(...),
    service: PermissionService = Depends(get_service),
):
    """Show all users who have access to a specific webapp."""
    try:
        perms = await service.list_for_webapp(webapp_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    from core.registry import AppRegistry
    app_info = AppRegistry.get_app(webapp_id)

    return templates.TemplateResponse(
        "admin_app/permissions_detail.html",
        {
            "request": request,
            "session": session,
            "title": f"Permissions — {webapp_id}",
            "filter_label": "webapp",
            "filter_value": webapp_id,
            "app_info": app_info,
            "permissions": perms,
            "back_url": "/admin/permissions/",
        },
    )


@router.get(
    "/user/{username}",
    response_class=HTMLResponse,
    name="admin:permissions_by_user",
)
async def permissions_by_user(
    request: Request,
    session: AdminOnly,
    username: str = Path(...),
    service: PermissionService = Depends(get_service),
):
    """Show all webapp permissions for a specific user."""
    try:
        perms = await service.list_for_user(username)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    from core.users import get_user_store
    user_record = get_user_store().get(username)

    return templates.TemplateResponse(
        "admin_app/permissions_detail.html",
        {
            "request": request,
            "session": session,
            "title": f"Permissions — {username}",
            "filter_label": "user",
            "filter_value": username,
            "user_record": user_record,
            "permissions": perms,
            "back_url": "/admin/permissions/",
        },
    )
