"""
Contact Repository — data access layer.

All DB queries are encapsulated here; services and routers
never touch SQLAlchemy directly.
"""
import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.example_app.models import Contact
from apps.example_app.schemas import ContactCreate, ContactUpdate

logger = logging.getLogger(__name__)


class DuplicateEmailError(Exception):
    pass


class ContactRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        department: Optional[str] = None,
    ) -> tuple[list[Contact], int]:
        """Return paginated contacts and total count."""
        query = select(Contact)

        if search:
            term = f"%{search.lower()}%"
            query = query.where(
                func.lower(Contact.name).like(term)
                | func.lower(Contact.email).like(term)
            )
        if department:
            query = query.where(Contact.department == department)

        # Count total
        count_q = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_q)
        total = total_result.scalar_one()

        # Paginate
        query = (
            query.order_by(Contact.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        contacts = list(result.scalars().all())

        return contacts, total

    async def get_by_id(self, contact_id: int) -> Optional[Contact]:
        result = await self.db.execute(
            select(Contact).where(Contact.id == contact_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Contact]:
        result = await self.db.execute(
            select(Contact).where(func.lower(Contact.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def create(self, data: ContactCreate) -> Contact:
        contact = Contact(**data.model_dump())
        self.db.add(contact)
        try:
            await self.db.flush()
            await self.db.refresh(contact)
        except IntegrityError:
            await self.db.rollback()
            raise DuplicateEmailError(f"Email '{data.email}' already exists")
        logger.info(f"Created contact id={contact.id} email={contact.email}")
        return contact

    async def update(self, contact: Contact, data: ContactUpdate) -> Contact:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(contact, field, value)
        try:
            await self.db.flush()
            await self.db.refresh(contact)
        except IntegrityError:
            await self.db.rollback()
            raise DuplicateEmailError(f"Email '{data.email}' already exists")
        logger.info(f"Updated contact id={contact.id}")
        return contact

    async def delete(self, contact: Contact) -> None:
        await self.db.delete(contact)
        await self.db.flush()
        logger.info(f"Deleted contact id={contact.id}")

    async def get_departments(self) -> list[str]:
        result = await self.db.execute(
            select(Contact.department)
            .where(Contact.department.isnot(None))
            .distinct()
            .order_by(Contact.department)
        )
        return [row[0] for row in result.all()]
