"""
Muteos router — CRUD endpoints for mute records.
"""
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.muteos_app.schemas import MuteoCreate
from apps.muteos_app.services import MuteoNotFoundError, MuteoService
from core.auth import UserSession, require_auth
from core.database import get_db
from core.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()

Auth = Annotated[UserSession, Depends(require_auth)]


def get_service(db: AsyncSession = Depends(get_db)) -> MuteoService:
    """Dependency: provides MuteoService instance."""
    return MuteoService(db)


def _base_ctx(request: Request, username: str) -> dict:
    """Build base template context with request and user info."""
    return {
        "request": request,
        "username": username,
    }


@router.get("/", response_class=HTMLResponse)
async def list_muteos(
    request: Request,
    session: Auth,
    service: MuteoService = Depends(get_service),
    page: int = Query(1, ge=1),
    componente: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """List all muteo records with pagination and optional filters."""
    try:
        muteos, total = await service.list_muteos(
            page=page,
            usuario=session.username,
            componente=componente,
            search=search,
        )
        total_pages = (total + 49) // 50  # 50 items per page

        ctx = _base_ctx(request, session.username)
        ctx.update({
            "muteos": muteos,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "componente_filter": componente or "",
            "search": search or "",
            "title": "Muteos",
        })
        return templates.TemplateResponse("muteos_app/muteo_list.html", ctx)
    except Exception as exc:
        logger.error(f"Error listing muteos: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error listing records") from exc


@router.get("/new", response_class=HTMLResponse)
async def new_muteo_form(request: Request, session: Auth):
    """Display the form to create a new muteo record."""
    ctx = _base_ctx(request, session.username)
    ctx.update({
        "errors": {},
        "title": "Report Mute",
        "form_action": "/apps/muteos/new",
        "submit_label": "Submit",
    })
    return templates.TemplateResponse("muteos_app/muteo_form.html", ctx)


@router.post("/new", response_class=HTMLResponse)
async def create_muteo(
    request: Request,
    session: Auth,
    service: MuteoService = Depends(get_service),
    componente: str = Form(..., min_length=1),
    ticket: str = Form(..., min_length=1),
    comentario: str = Form(..., min_length=1),
):
    """Create a new muteo record."""
    errors = {}
    try:
        data = MuteoCreate(
            componente=componente.strip(),
            ticket=ticket.strip(),
            comentario=comentario.strip(),
        )
        muteo = await service.create_muteo(data, usuario=session.username)
        logger.info(f"Muteo #{muteo.id} created by {session.username}")
        
        return RedirectResponse(
            url=f"/apps/muteos/?created=1&id={muteo.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as exc:
        errors["general"] = str(exc)
        logger.warning(f"Validation error creating muteo: {exc}")
    except Exception as exc:
        errors["general"] = "An error occurred while creating the record. Please try again."
        logger.error(f"Error creating muteo: {exc}", exc_info=True)

    ctx = _base_ctx(request, session.username)
    ctx.update({
        "errors": errors,
        "title": "Report Mute",
        "form_action": "/apps/muteos/new",
        "submit_label": "Submit",
        "componente": componente,
        "ticket": ticket,
        "comentario": comentario,
    })
    return templates.TemplateResponse("muteos_app/muteo_form.html", ctx, status_code=400)


@router.get("/{muteo_id}", response_class=HTMLResponse)
async def view_muteo(
    request: Request,
    session: Auth,
    muteo_id: int,
    service: MuteoService = Depends(get_service),
):
    """View details of a single muteo record."""
    try:
        muteo = await service.get_muteo(muteo_id)
        
        ctx = _base_ctx(request, session.username)
        ctx.update({
            "muteo": muteo,
            "title": f"Muteo #{muteo_id}",
        })
        return templates.TemplateResponse("muteos_app/muteo_detail.html", ctx)
    except MuteoNotFoundError:
        raise HTTPException(status_code=404, detail="Muteo not found") from None


@router.post("/{muteo_id}/delete")
async def delete_muteo(
    muteo_id: int,
    session: Auth,
    service: MuteoService = Depends(get_service),
):
    """Delete a muteo record (only by creator)."""
    try:
        muteo = await service.get_muteo(muteo_id)
        
        # Only allow deletion by creator
        if muteo.usuario != session.username:
            raise HTTPException(status_code=403, detail="You can only delete your own records")
        
        await service.delete_muteo(muteo_id)
        logger.info(f"Muteo #{muteo_id} deleted by {session.username}")
        
        return RedirectResponse(
            url="/apps/muteos/?deleted=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except MuteoNotFoundError:
        raise HTTPException(status_code=404, detail="Muteo not found") from None
