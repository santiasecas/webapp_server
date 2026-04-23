"""
Middleware configuration.

Execution order (outermost → innermost):
  1. RequestLoggingMiddleware   — assigns request ID, logs timing
  2. SessionRedirectMiddleware  — checks auth cookie + webapp permissions

Permission check in SessionRedirectMiddleware:
  - Path matches /apps/<something>  → extract webapp_id from prefix
  - Webapp has permission_required=True → query DB
  - Admin users → always allowed (no DB hit)
  - Open apps  → always allowed (no DB hit)
  - No permission row → 403 page
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

logger = logging.getLogger(__name__)


def _is_public(path: str) -> bool:
    return any(path.startswith(p) for p in settings.PUBLIC_PATHS)


class SessionRedirectMiddleware(BaseHTTPMiddleware):
    """
    Gate 1 — Authentication:
      Public paths           → pass through
      Valid session cookie   → proceed to Gate 2
      No/invalid cookie      → redirect to /login?next=<path>

    Gate 2 — Webapp permission (only for /apps/* paths):
      Admin user             → always pass
      App not permission_required → pass
      User has DB permission → pass
      Otherwise              → 403 Forbidden page
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Gate 1 — Public paths bypass everything
        if _is_public(request.url.path):
            return await call_next(request)

        # Gate 1 — Session check
        from core.auth import get_session
        session = get_session(request)
        if session is None:
            next_url = request.url.path
            if request.url.query:
                next_url += f"?{request.url.query}"
            logger.debug(f"Unauthenticated → /login  path={request.url.path}")
            return RedirectResponse(url=f"/login?next={next_url}", status_code=302)

        # Attach session for downstream handlers
        request.state.session = session

        # Gate 2 — Webapp permission check (only for /apps/* routes)
        if request.url.path.startswith("/apps/"):
            from core.registry import AppRegistry
            app_info = AppRegistry.get_app_by_prefix(request.url.path)

            if app_info is not None and app_info.get("permission_required", False):
                # Admins always have access — skip DB
                if not session.is_admin:
                    allowed = await self._check_permission(
                        session.username, app_info["name"]
                    )
                    if not allowed:
                        logger.warning(
                            f"Permission denied: user={session.username!r} "
                            f"webapp={app_info['name']!r} path={request.url.path}"
                        )
                        return await self._forbidden_response(request, app_info)

        return await call_next(request)

    async def _check_permission(self, username: str, webapp_id: str) -> bool:
        """Open a DB session and check the permission table."""
        try:
            from core.database import AsyncSessionFactory
            from core.permissions import PermissionRepository
            async with AsyncSessionFactory() as db:
                repo = PermissionRepository(db)
                return await repo.has_permission(username, webapp_id)
        except Exception as e:
            logger.error(f"Permission DB check failed: {e}")
            return False  # Deny on error — fail secure

    async def _forbidden_response(self, request: Request, app_info: dict) -> Response:
        """Return a proper 403 HTML page."""
        try:
            from core.templates import templates
            return templates.TemplateResponse(
                "base/error.html",
                {
                    "request": request,
                    "status_code": 403,
                    "detail": (
                        f"You don't have permission to access "
                        f"'{app_info['name'].replace('_', ' ').title()}'. "
                        f"Contact an administrator to request access."
                    ),
                },
                status_code=403,
            )
        except Exception:
            from fastapi.responses import HTMLResponse
            return HTMLResponse(
                "<h1>403 Forbidden</h1><p>You do not have access to this application.</p>",
                status_code=403,
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs each request with timing and request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        user = getattr(getattr(request.state, "session", None), "username", "-")
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"→ {response.status_code} ({elapsed_ms:.1f}ms) user={user}"
        )
        response.headers["X-Request-ID"] = request_id
        return response


def setup_middleware(app: FastAPI) -> None:
    """Register all platform middleware. Last added = outermost."""

    app.add_middleware(SessionRedirectMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    if settings.ENVIRONMENT == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[f"http://{settings.HOST}:{settings.PORT}"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )
