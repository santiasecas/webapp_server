"""
Corporate Platform - Main Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import Base, engine
from core.error_handlers import register_error_handlers
from core.logging_config import setup_logging
from core.middleware import setup_middleware
from core.registry import AppRegistry

# Import apps to register them — order determines sidebar position
from apps.admin_app import app_module as _admin_module       # noqa: F401
from apps.example_app import app_module                      # noqa: F401
from apps.tickets_app import app_module as _tickets_module   # noqa: F401
from apps.muteos_app import app_module as _muteos_module

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Corporate Platform...")
    logger.info(f"Environment: {settings.ENVIRONMENT}  |  Debug: {settings.DEBUG}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created.")

    for app_name, info in AppRegistry.apps.items():
        logger.info(f"  ✓ App registered: '{app_name}' at {info['prefix']}")

    logger.info("Platform ready.")
    yield
    logger.info("Shutting down Corporate Platform...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
setup_middleware(app)
register_error_handlers(app)

for app_name, info in AppRegistry.apps.items():
    app.mount(info["prefix"], info["router"], name=app_name)


# ── Core routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, tags=["Core"])
async def root(request: Request):
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse, tags=["Core"])
async def dashboard(request: Request):
    from core.auth import require_auth
    from core.templates import templates
    session = require_auth(request)          # raises _RedirectToLogin if not authed
    return templates.TemplateResponse(
        "base/dashboard.html",
        {"request": request, "session": session, "title": "Dashboard"},
    )


@app.get("/health", tags=["Core"])
async def healthcheck():
    from sqlalchemy import text
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.warning(f"Health check DB error: {e}")

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "registered_apps": list(AppRegistry.apps.keys()),
    }


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_page(request: Request, next: str = "/dashboard", error: str = ""):
    """Show the login form. If already authenticated, redirect to dashboard."""
    from core.auth import get_session
    from core.templates import templates

    if get_session(request) is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(
        "base/login.html",
        {
            "request": request,
            "next": next,
            "error": error,
            "title": "Login",
        },
    )


@app.post("/login", tags=["Auth"])
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard"),
):
    """Process login form. On success, set session cookie and redirect."""
    from core.auth import COOKIE_NAME, create_session_cookie
    from core.templates import templates
    from core.users import get_user_store

    store = get_user_store()
    user = store.verify(username.strip(), password)

    if user is None:
        logger.warning(f"Failed login: user='{username}' ip={request.client.host}")
        return templates.TemplateResponse(
            "base/login.html",
            {
                "request": request,
                "next": next,
                "error": "Invalid username or password.",
                "title": "Login",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    logger.info(f"Login: user='{username}' groups={user.groups} ip={request.client.host}")

    # Sanitise redirect target — never redirect to external URLs
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/dashboard"

    response = RedirectResponse(url=safe_next, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_cookie(user.username, user.groups, user.display_name),
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
    )
    return response


@app.get("/logout", tags=["Auth"])
async def logout(request: Request):
    """Clear session cookie and redirect to login."""
    from core.auth import COOKIE_NAME
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")
    logger.info(f"Logout: ip={request.client.host}")
    return response
