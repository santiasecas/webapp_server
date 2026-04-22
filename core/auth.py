"""
core/auth.py — Session-based authentication with group/role support.

Flow:
  1. Unauthenticated request → redirect to /login
  2. POST /login → verify credentials → set signed cookie → redirect to original URL
  3. GET /logout → clear cookie → redirect to /login

Session cookie:
  - Signed with itsdangerous (HMAC-SHA256) using SECRET_KEY
  - Contains: {"u": username, "g": [groups...], "dn": display_name}
  - HttpOnly, SameSite=Lax
  - Lifetime controlled by SESSION_MAX_AGE (seconds)

FastAPI dependencies (all raise HTTP 302 or 403, never 401):
  require_auth                           → any authenticated user
  require_group("admins")                → user must be in "admins"
  require_group("admins", "editors")     → user must be in one of those groups
  optional_session                       → returns session or None, never raises
"""
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.config import settings

logger = logging.getLogger(__name__)

_signer: Optional[URLSafeTimedSerializer] = None


def _get_signer() -> URLSafeTimedSerializer:
    global _signer
    if _signer is None:
        _signer = URLSafeTimedSerializer(
            secret_key=settings.SECRET_KEY,
            salt="session-auth",
        )
    return _signer


# ── Session data ──────────────────────────────────────────────────────────────

@dataclass
class UserSession:
    username: str
    groups: list[str]
    display_name: str = ""

    def has_group(self, group: str) -> bool:
        return group in self.groups

    def has_any_group(self, *groups: str) -> bool:
        return any(g in self.groups for g in groups)

    def has_all_groups(self, *groups: str) -> bool:
        return all(g in self.groups for g in groups)

    @property
    def primary_group(self) -> str:
        return self.groups[0] if self.groups else "users"

    @property
    def is_admin(self) -> bool:
        return "admins" in self.groups


# ── Cookie helpers ────────────────────────────────────────────────────────────

COOKIE_NAME = "platform_session"


def create_session_cookie(username: str, groups: list[str], display_name: str) -> str:
    return _get_signer().dumps({"u": username, "g": groups, "dn": display_name})


def read_session_cookie(cookie_value: str) -> Optional[UserSession]:
    try:
        data = _get_signer().loads(cookie_value, max_age=settings.SESSION_MAX_AGE)
        return UserSession(
            username=data["u"],
            groups=data.get("g", ["users"]),
            display_name=data.get("dn", data["u"]),
        )
    except SignatureExpired:
        logger.debug("Session cookie expired")
        return None
    except (BadSignature, KeyError, Exception) as e:
        logger.debug(f"Invalid session cookie: {e}")
        return None


def get_session(request: Request) -> Optional[UserSession]:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return read_session_cookie(cookie)


def _login_redirect(request: Request) -> RedirectResponse:
    next_url = request.url.path
    if request.url.query:
        next_url += f"?{request.url.query}"
    return RedirectResponse(url=f"/login?next={next_url}", status_code=status.HTTP_302_FOUND)


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def require_auth(request: Request) -> UserSession:
    """
    Dependency: user must be logged in.
    Raises _RedirectToLogin (caught by error handler) if not authenticated.

    Usage:
        session: UserSession = Depends(require_auth)
    """
    session = get_session(request)
    if session is None:
        raise _RedirectToLogin(request)
    return session


def require_group(*groups: str):
    """
    Dependency factory: user must belong to at least one of the given groups.

    Usage:
        Depends(require_group("admins"))
        Depends(require_group("admins", "editors"))
    """
    def _dependency(request: Request) -> UserSession:
        session = get_session(request)
        if session is None:
            raise _RedirectToLogin(request)
        if not session.has_any_group(*groups):
            logger.warning(
                f"User '{session.username}' (groups={session.groups}) denied "
                f"access to {request.url.path} — requires one of {list(groups)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required: {' or '.join(groups)}",
            )
        return session
    return _dependency


def require_all_groups(*groups: str):
    """Dependency factory: user must belong to ALL of the given groups."""
    def _dependency(request: Request) -> UserSession:
        session = get_session(request)
        if session is None:
            raise _RedirectToLogin(request)
        missing = [g for g in groups if not session.has_group(g)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Missing groups: {', '.join(missing)}",
            )
        return session
    return _dependency


def optional_session(request: Request) -> Optional[UserSession]:
    """Dependency: returns session if logged in, None otherwise. Never redirects."""
    return get_session(request)


# ── Internal redirect exception ───────────────────────────────────────────────

class _RedirectToLogin(Exception):
    """Raised by auth dependencies to trigger a redirect to /login."""
    def __init__(self, request: Request):
        self.request = request


# ── Legacy compatibility ──────────────────────────────────────────────────────
# Keep hash_password_bcrypt importable from core.auth (used in scripts)
from core.auth_passwords import hash_password_bcrypt, verify_password  # noqa: F401, E402
