"""
Middleware configuration.

SessionRedirectMiddleware: intercepts every request, checks session cookie,
redirects to /login for protected paths. This is the single enforcement point —
individual route dependencies (require_auth, require_group) provide finer control.
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
    """Returns True if the path does not require a session check."""
    return any(path.startswith(p) for p in settings.PUBLIC_PATHS)


class SessionRedirectMiddleware(BaseHTTPMiddleware):
    """
    Intercepts all requests:
      - Public paths → pass through
      - Has valid session cookie → pass through
      - No/invalid cookie → 302 to /login?next=<original_path>
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Always allow public paths
        if _is_public(request.url.path):
            return await call_next(request)

        # Check for valid session cookie
        from core.auth import get_session, _RedirectToLogin
        session = get_session(request)
        if session is None:
            next_url = request.url.path
            if request.url.query:
                next_url += f"?{request.url.query}"
            logger.debug(f"Unauthenticated access to {request.url.path} → redirect to /login")
            return RedirectResponse(
                url=f"/login?next={next_url}",
                status_code=302,
            )

        # Attach session to request state so handlers can access it without Depends
        request.state.session = session
        return await call_next(request)


class WebappPermissionMiddleware(BaseHTTPMiddleware):
    """
    Verifies user has access to requested webapp.
    
    Rules:
    - Admins have access to all webapps
    - Regular users need explicit permission
    - Bypass for non-webapp paths
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip permission check for non-webapp paths
        if not request.url.path.startswith("/apps/"):
            return await call_next(request)

        # Get session (should already be attached by SessionRedirectMiddleware)
        session = getattr(request.state, "session", None)
        if session is None:
            # This shouldn't happen if SessionRedirectMiddleware worked correctly
            return RedirectResponse(url="/login", status_code=302)

        # Admins bypass permission check
        if session.has_group("admins"):
            return await call_next(request)

        # Extract webapp_id from path (e.g., /apps/tickets/ → 'tickets_app')
        # Path format: /apps/{webapp_name}/ or /apps/{webapp_name}/...
        parts = request.url.path.strip("/").split("/")
        if len(parts) < 2:
            return RedirectResponse(url="/dashboard", status_code=302)

        webapp_name = parts[1]  # e.g., 'tickets'
        
        # Map webapp name to webapp_id
        # Convention: 'tickets' → 'tickets_app'
        from core.registry import AppRegistry
        
        # Find matching app
        webapp_id = None
        for app_id, app_info in AppRegistry.apps.items():
            if app_info["prefix"] == f"/apps/{webapp_name}":
                webapp_id = app_id
                break

        if not webapp_id:
            # Webapp not found, let it through (will 404 naturally)
            return await call_next(request)

        # Check permission asynchronously
        try:
            from core.database import AsyncSessionFactory
            from core.permissions_service import PermissionService
            from core.users import user_store

            async with AsyncSessionFactory() as db:
                service = PermissionService(db, user_store)
                has_access = await service.check_access(
                    session.username,
                    webapp_id,
                    session.groups,
                )

            if not has_access:
                logger.warning(
                    f"Access denied: {session.username} tried to access {webapp_id} "
                    f"from {request.url.path}"
                )
                return RedirectResponse(
                    url=f"/dashboard?error=Access+denied+to+{webapp_id}",
                    status_code=302,
                )
        except Exception as e:
            logger.error(f"Error checking webapp permission: {e}", exc_info=True)
            # On error, deny access (fail closed)
            return RedirectResponse(url="/dashboard?error=Permission+check+failed", status_code=302)

        return await call_next(request)


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
    """Register all platform middleware. Order matters — last added = outermost."""

    # Innermost: permissions check (runs after session validation)
    app.add_middleware(WebappPermissionMiddleware)

    # Session redirect (runs after permissions check)
    app.add_middleware(SessionRedirectMiddleware)

    # Outermost: request logging (wraps everything)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS
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
