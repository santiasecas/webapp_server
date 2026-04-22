"""
Jinja2 template engine setup with custom filters, globals, and automatic
session injection so every template has access to the current user session.
"""
from datetime import datetime
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import Response
from starlette.templating import _TemplateResponse  # noqa: F401 (type reference)

from core.config import settings


class _PlatformTemplates(Jinja2Templates):
    """
    Subclass of Jinja2Templates that automatically injects:
      - session: UserSession | None   (from request cookie, every page)
    into every TemplateResponse context so the layout and any template
    can access the current user without the router explicitly passing it.
    """

    def TemplateResponse(  # type: ignore[override]
        self,
        name: str,
        context: dict[str, Any],
        status_code: int = 200,
        headers: dict | None = None,
        media_type: str | None = None,
        background=None,
    ) -> Response:
        # Auto-inject session if not already provided
        if "session" not in context:
            request: Request = context.get("request")
            if request is not None:
                from core.auth import get_session
                context["session"] = get_session(request)

        return super().TemplateResponse(
            name,
            context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )


templates = _PlatformTemplates(directory=settings.TEMPLATES_DIR)

# ── Global template variables ────────────────────────────────────────────────
templates.env.globals["app_title"] = settings.APP_TITLE
templates.env.globals["app_version"] = settings.APP_VERSION
templates.env.globals["environment"] = settings.ENVIRONMENT
templates.env.globals["debug"] = settings.DEBUG


def _get_registered_apps():
    """
    Lazy getter — called at render time so apps registered AFTER
    templates.py is imported are still visible in the sidebar.
    """
    from core.registry import AppRegistry
    return AppRegistry.get_app_list()


# Inject apps list into every template automatically.
templates.env.globals["apps"] = _get_registered_apps


# ── Custom filters ───────────────────────────────────────────────────────────
def _format_datetime(value, fmt="%d/%m/%Y %H:%M"):
    if value is None:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime(fmt)


def _format_date(value, fmt="%d/%m/%Y"):
    return _format_datetime(value, fmt)


def _nl2br(value: str) -> str:
    return value.replace("\n", "<br>") if value else ""


templates.env.filters["datetime"] = _format_datetime
templates.env.filters["date"] = _format_date
templates.env.filters["nl2br"] = _nl2br
