"""
Contact Service — business logic layer.

Services coordinate repositories and apply business rules.
They are the layer between HTTP handlers and the database.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from apps.example_app.repositories import ContactRepository, DuplicateEmailError
from apps.example_app.schemas import ContactCreate, ContactListResponse, ContactRead, ContactUpdate

logger = logging.getLogger(__name__)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


class ContactNotFoundError(Exception):
    pass


class ContactService:

    def __init__(self, db: AsyncSession):
        self.repo = ContactRepository(db)

    async def list_contacts(
        self,
        page: int = 1,
        page_size: int = PAGE_SIZE_DEFAULT,
        search: Optional[str] = None,
        department: Optional[str] = None,
    ) -> ContactListResponse:
        page = max(1, page)
        page_size = min(max(1, page_size), PAGE_SIZE_MAX)

        contacts, total = await self.repo.get_all(
            page=page,
            page_size=page_size,
            search=search,
            department=department,
        )
        return ContactListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[ContactRead.model_validate(c) for c in contacts],
        )

    async def get_contact(self, contact_id: int) -> ContactRead:
        contact = await self.repo.get_by_id(contact_id)
        if not contact:
            raise ContactNotFoundError(f"Contact {contact_id} not found")
        return ContactRead.model_validate(contact)

    async def create_contact(self, data: ContactCreate) -> ContactRead:
        contact = await self.repo.create(data)
        return ContactRead.model_validate(contact)

    async def update_contact(self, contact_id: int, data: ContactUpdate) -> ContactRead:
        contact = await self.repo.get_by_id(contact_id)
        if not contact:
            raise ContactNotFoundError(f"Contact {contact_id} not found")
        updated = await self.repo.update(contact, data)
        return ContactRead.model_validate(updated)

    async def delete_contact(self, contact_id: int) -> None:
        contact = await self.repo.get_by_id(contact_id)
        if not contact:
            raise ContactNotFoundError(f"Contact {contact_id} not found")
        await self.repo.delete(contact)

    async def get_departments(self) -> list[str]:
        return await self.repo.get_departments()
