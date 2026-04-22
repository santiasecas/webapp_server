"""
Ticket repository — data access layer.
"""
import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.tickets_app.models import Ticket, TicketPriority, TicketStatus
from apps.tickets_app.schemas import TicketCreate, TicketUpdate

logger = logging.getLogger(__name__)


class TicketRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 25,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Ticket], int]:
        query = select(Ticket)

        if status:
            query = query.where(Ticket.status == status)
        if priority:
            query = query.where(Ticket.priority == priority)
        if assigned_to:
            query = query.where(Ticket.assigned_to == assigned_to)
        if search:
            term = f"%{search.lower()}%"
            query = query.where(func.lower(Ticket.title).like(term))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        query = (
            query.order_by(Ticket.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, ticket_id: int) -> Optional[Ticket]:
        r = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id))
        return r.scalar_one_or_none()

    async def create(self, data: TicketCreate) -> Ticket:
        ticket = Ticket(**data.model_dump())
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        logger.info(f"Created ticket id={ticket.id}: {ticket.title!r}")
        return ticket

    async def update(self, ticket: Ticket, data: TicketUpdate) -> Ticket:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(ticket, field, value)
        await self.db.flush()
        await self.db.refresh(ticket)
        logger.info(f"Updated ticket id={ticket.id}")
        return ticket

    async def delete(self, ticket: Ticket) -> None:
        await self.db.delete(ticket)
        await self.db.flush()
        logger.info(f"Deleted ticket id={ticket.id}")

    async def get_stats(self) -> dict:
        """Count tickets by status for dashboard widget."""
        result = await self.db.execute(
            select(Ticket.status, func.count(Ticket.id))
            .group_by(Ticket.status)
        )
        return {row[0]: row[1] for row in result.all()}
