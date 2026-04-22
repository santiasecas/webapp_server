"""
Tickets router — full CRUD + quick status update.
"""
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.tickets_app.models import TicketPriority, TicketStatus
from apps.tickets_app.schemas import (
    PRIORITY_LABELS, STATUS_LABELS,
    TicketCreate, TicketUpdate,
)
from apps.tickets_app.services import TicketNotFoundError, TicketService
from core.auth import require_auth, UserSession
from core.database import get_db
from core.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()

Auth = Annotated[UserSession, Depends(require_auth)]

# Template context helpers
_STATUS_OPTIONS = [{"value": s.value, "label": l} for s, (l, _) in STATUS_LABELS.items()]
_PRIORITY_OPTIONS = [{"value": p.value, "label": l} for p, (l, _) in PRIORITY_LABELS.items()]


def get_service(db: AsyncSession = Depends(get_db)) -> TicketService:
    return TicketService(db)


def _base_ctx(request: Request, username: str) -> dict:
    return {
        "request": request,
        "username": username,
        "status_options": _STATUS_OPTIONS,
        "priority_options": _PRIORITY_OPTIONS,
        "status_labels": STATUS_LABELS,
        "priority_labels": PRIORITY_LABELS,
        "TicketStatus": TicketStatus,
        "TicketPriority": TicketPriority,
    }


@router.get("/", response_class=HTMLResponse)
async def list_tickets(
    request: Request,
    session: Auth,
    service: TicketService = Depends(get_service),
    page: int = Query(1, ge=1),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    search: Optional[str] = Query(None),
):
    # Parse optional enum filters
    status_val = TicketStatus(status_filter) if status_filter else None
    priority_val = TicketPriority(priority_filter) if priority_filter else None

    tickets, total = await service.list_tickets(
        page=page, status=status_val, priority=priority_val, search=search
    )
    stats = await service.get_stats()
    total_pages = (total + 24) // 25

    ctx = _base_ctx(request, session.username)
    ctx.update({
        "tickets": tickets,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "stats": stats,
        "search": search or "",
        "status_filter": status_filter or "",
        "priority_filter": priority_filter or "",
        "title": "Tickets",
    })
    return templates.TemplateResponse("tickets_app/ticket_list.html", ctx)


@router.get("/new", response_class=HTMLResponse)
async def new_ticket_form(request: Request, session: Auth):
    ctx = _base_ctx(request, session.username)
    ctx.update({
        "ticket": None, "errors": {},
        "title": "New Ticket",
        "form_action": "/apps/tickets/new",
        "submit_label": "Open Ticket",
    })
    return templates.TemplateResponse("tickets_app/ticket_form.html", ctx)


@router.post("/new", response_class=HTMLResponse)
async def create_ticket(
    request: Request,
    session: Auth,
    service: TicketService = Depends(get_service),
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("medium"),
    assigned_to: str = Form(""),
):
    errors = {}
    try:
        data = TicketCreate(
            title=title,
            description=description or None,
            priority=TicketPriority(priority),
            assigned_to=assigned_to or None,
            reporter=session.username,
        )
        ticket = await service.create_ticket(data)
        return RedirectResponse(
            url=f"/apps/tickets/{ticket.id}?created=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValueError as exc:
        errors["general"] = str(exc)

    ctx = _base_ctx(request, session.username)
    ctx.update({
        "ticket": {"title": title, "description": description,
                   "priority": priority, "assigned_to": assigned_to},
        "errors": errors,
        "title": "New Ticket",
        "form_action": "/apps/tickets/new",
        "submit_label": "Open Ticket",
    })
    return templates.TemplateResponse(
        "tickets_app/ticket_form.html", ctx,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@router.get("/{ticket_id}", response_class=HTMLResponse)
async def view_ticket(
    request: Request,
    ticket_id: int,
    session: Auth,
    service: TicketService = Depends(get_service),
):
    try:
        ticket = await service.get_ticket(ticket_id)
    except TicketNotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ctx = _base_ctx(request, session.username)
    ctx.update({"ticket": ticket, "title": f"#{ticket.id}: {ticket.title}"})
    return templates.TemplateResponse("tickets_app/ticket_detail.html", ctx)


@router.get("/{ticket_id}/edit", response_class=HTMLResponse)
async def edit_ticket_form(
    request: Request,
    ticket_id: int,
    session: Auth,
    service: TicketService = Depends(get_service),
):
    try:
        ticket = await service.get_ticket(ticket_id)
    except TicketNotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ctx = _base_ctx(request, session.username)
    ctx.update({
        "ticket": ticket, "errors": {},
        "title": f"Edit #{ticket_id}",
        "form_action": f"/apps/tickets/{ticket_id}/edit",
        "submit_label": "Save Changes",
    })
    return templates.TemplateResponse("tickets_app/ticket_form.html", ctx)


@router.post("/{ticket_id}/edit", response_class=HTMLResponse)
async def update_ticket(
    request: Request,
    ticket_id: int,
    session: Auth,
    service: TicketService = Depends(get_service),
    title: str = Form(...),
    description: str = Form(""),
    status_val: str = Form(..., alias="status"),
    priority: str = Form("medium"),
    assigned_to: str = Form(""),
):
    errors = {}
    try:
        data = TicketUpdate(
            title=title,
            description=description or None,
            status=TicketStatus(status_val),
            priority=TicketPriority(priority),
            assigned_to=assigned_to or None,
        )
        await service.update_ticket(ticket_id, data)
        return RedirectResponse(
            url=f"/apps/tickets/{ticket_id}?updated=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except TicketNotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")
    except ValueError as exc:
        errors["general"] = str(exc)

    ctx = _base_ctx(request, session.username)
    ctx.update({
        "ticket": {"id": ticket_id, "title": title, "description": description,
                   "status": status_val, "priority": priority, "assigned_to": assigned_to},
        "errors": errors,
        "title": f"Edit #{ticket_id}",
        "form_action": f"/apps/tickets/{ticket_id}/edit",
        "submit_label": "Save Changes",
    })
    return templates.TemplateResponse(
        "tickets_app/ticket_form.html", ctx,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@router.post("/{ticket_id}/delete")
async def delete_ticket(
    ticket_id: int,
    session: Auth,
    service: TicketService = Depends(get_service),
):
    try:
        await service.delete_ticket(ticket_id)
    except TicketNotFoundError:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return RedirectResponse(
        url="/apps/tickets/?deleted=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )
