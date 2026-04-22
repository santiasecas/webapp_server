"""
Global error handlers.
"""
import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.config import settings

logger = logging.getLogger(__name__)


def _wants_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


async def _html_error(request: Request, status_code: int, detail: str) -> HTMLResponse:
    try:
        from core.templates import templates
        return templates.TemplateResponse(
            "base/error.html",
            {"request": request, "status_code": status_code, "detail": detail},
            status_code=status_code,
        )
    except Exception:
        return HTMLResponse(
            content=f"<h1>{status_code} Error</h1><p>{detail}</p>",
            status_code=status_code,
        )


def register_error_handlers(app: FastAPI) -> None:

    # ── Handle auth redirect exceptions ──────────────────────────────────────
    from core.auth import _RedirectToLogin

    @app.exception_handler(_RedirectToLogin)
    async def redirect_to_login_handler(request: Request, exc: _RedirectToLogin):
        next_url = exc.request.url.path
        if exc.request.url.query:
            next_url += f"?{exc.request.url.query}"
        return RedirectResponse(url=f"/login?next={next_url}", status_code=302)

    # ── HTTP exceptions ───────────────────────────────────────────────────────
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # 403 → show forbidden page (not redirect to login)
        if _wants_json(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers or {},
            )
        return await _html_error(request, exc.status_code, str(exc.detail))

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        if _wants_json(request):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return await _html_error(request, 404, f"Page not found: {request.url.path}")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
        detail = f"{exc}" if settings.DEBUG else "An unexpected error occurred."
        if _wants_json(request):
            return JSONResponse(status_code=500, content={"detail": detail})
        return await _html_error(request, 500, detail)
