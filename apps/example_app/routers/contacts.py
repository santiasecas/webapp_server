"""
Contacts router — handles both HTML (browser) and JSON (API) responses.

All routes require authentication via require_auth dependency.
"""
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.example_app.repositories import DuplicateEmailError
from apps.example_app.schemas import ContactCreate, ContactUpdate
from apps.example_app.services import ContactNotFoundError, ContactService
from core.auth import require_auth, UserSession
from core.database import get_db
from core.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Dependency shorthand ──────────────────────────────────────────────────────
Auth = Annotated[UserSession, Depends(require_auth)]


def get_service(db: AsyncSession = Depends(get_db)) -> ContactService:
    return ContactService(db)


# ── HTML routes ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def list_contacts_html(
    request: Request,
    session: Auth,
    service: ContactService = Depends(get_service),
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
):
    result = await service.list_contacts(
        page=page, search=search, department=department
    )
    departments = await service.get_departments()
    total_pages = (result.total + result.page_size - 1) // result.page_size

    return templates.TemplateResponse(
        "example_app/contact_list.html",
        {
            "request": request,
            "username": session.username,
            "contacts": result.items,
            "total": result.total,
            "page": result.page,
            "total_pages": total_pages,
            "search": search or "",
            "departments": departments,
            "selected_dept": department or "",
            "title": "Contacts",
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_contact_form(
    request: Request,
    session: Auth,
    service: ContactService = Depends(get_service),
):
    departments = await service.get_departments()
    return templates.TemplateResponse(
        "example_app/contact_form.html",
        {
            "request": request,
            "username": session.username,
            "contact": None,
            "departments": departments,
            "errors": {},
            "title": "New Contact",
            "form_action": "/apps/contacts/new",
            "submit_label": "Create Contact",
        },
    )


@router.post("/new", response_class=HTMLResponse)
async def create_contact_html(
    request: Request,
    session: Auth,
    service: ContactService = Depends(get_service),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    department: str = Form(""),
    notes: str = Form(""),
):
    errors = {}
    try:
        data = ContactCreate(
            name=name,
            email=email,
            phone=phone or None,
            department=department or None,
            notes=notes or None,
        )
        await service.create_contact(data)
        return RedirectResponse(
            url="/apps/contacts/?created=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except DuplicateEmailError:
        errors["email"] = f"Email '{email}' is already registered"
    except ValueError as exc:
        # Pydantic validation errors
        for err in exc.errors() if hasattr(exc, "errors") else []:
            field = err["loc"][-1] if err.get("loc") else "general"
            errors[field] = err["msg"]
        if not errors:
            errors["general"] = str(exc)

    departments = await service.get_departments()
    return templates.TemplateResponse(
        "example_app/contact_form.html",
        {
            "request": request,
            "username": session.username,
            "contact": {"name": name, "email": email, "phone": phone,
                        "department": department, "notes": notes},
            "departments": departments,
            "errors": errors,
            "title": "New Contact",
            "form_action": "/apps/contacts/new",
            "submit_label": "Create Contact",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@router.get("/{contact_id}", response_class=HTMLResponse)
async def view_contact(
    request: Request,
    contact_id: int,
    session: Auth,
    service: ContactService = Depends(get_service),
):
    try:
        contact = await service.get_contact(contact_id)
    except ContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    return templates.TemplateResponse(
        "example_app/contact_detail.html",
        {
            "request": request,
            "username": session.username,
            "contact": contact,
            "title": contact.name,
        },
    )


@router.get("/{contact_id}/edit", response_class=HTMLResponse)
async def edit_contact_form(
    request: Request,
    contact_id: int,
    session: Auth,
    service: ContactService = Depends(get_service),
):
    try:
        contact = await service.get_contact(contact_id)
    except ContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    departments = await service.get_departments()
    return templates.TemplateResponse(
        "example_app/contact_form.html",
        {
            "request": request,
            "username": session.username,
            "contact": contact,
            "departments": departments,
            "errors": {},
            "title": f"Edit: {contact.name}",
            "form_action": f"/apps/contacts/{contact_id}/edit",
            "submit_label": "Save Changes",
        },
    )


@router.post("/{contact_id}/edit", response_class=HTMLResponse)
async def update_contact_html(
    request: Request,
    contact_id: int,
    session: Auth,
    service: ContactService = Depends(get_service),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    department: str = Form(""),
    notes: str = Form(""),
):
    errors = {}
    try:
        data = ContactUpdate(
            name=name,
            email=email,
            phone=phone or None,
            department=department or None,
            notes=notes or None,
        )
        await service.update_contact(contact_id, data)
        return RedirectResponse(
            url=f"/apps/contacts/{contact_id}?updated=1",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    except DuplicateEmailError:
        errors["email"] = f"Email '{email}' is already registered"
    except ValueError as exc:
        errors["general"] = str(exc)

    departments = await service.get_departments()
    return templates.TemplateResponse(
        "example_app/contact_form.html",
        {
            "request": request,
            "username": session.username,
            "contact": {"id": contact_id, "name": name, "email": email,
                        "phone": phone, "department": department, "notes": notes},
            "departments": departments,
            "errors": errors,
            "title": "Edit Contact",
            "form_action": f"/apps/contacts/{contact_id}/edit",
            "submit_label": "Save Changes",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@router.post("/{contact_id}/delete")
async def delete_contact(
    contact_id: int,
    session: Auth,
    service: ContactService = Depends(get_service),
):
    try:
        await service.delete_contact(contact_id)
    except ContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    return RedirectResponse(
        url="/apps/contacts/?deleted=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ── JSON API routes (bonus) ───────────────────────────────────────────────────

@router.get("/api/contacts")
async def list_contacts_json(
    session: Auth,
    service: ContactService = Depends(get_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
):
    return await service.list_contacts(page=page, page_size=page_size, search=search)
