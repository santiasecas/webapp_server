"""
Ticket service — business logic.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from apps.tickets_app.models import TicketPriority, TicketStatus
from apps.tickets_app.repositories import TicketRepository
from apps.tickets_app.schemas import TicketCreate, TicketRead, TicketUpdate

logger = logging.getLogger(__name__)


class TicketNotFoundError(Exception):
    pass


class TicketService:

    def __init__(self, db: AsyncSession):
        self.repo = TicketRepository(db)

    async def list_tickets(
        self,
        page: int = 1,
        page_size: int = 25,
        status: Optional[TicketStatus] = None,
        priority: Optional[TicketPriority] = None,
        assigned_to: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[TicketRead], int]:
        tickets, total = await self.repo.get_all(
            page=page, page_size=page_size,
            status=status, priority=priority,
            assigned_to=assigned_to, search=search,
        )
        return [TicketRead.model_validate(t) for t in tickets], total

    async def get_ticket(self, ticket_id: int) -> TicketRead:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} not found")
        return TicketRead.model_validate(ticket)

    async def create_ticket(self, data: TicketCreate) -> TicketRead:
        ticket = await self.repo.create(data)
        return TicketRead.model_validate(ticket)

    async def update_ticket(self, ticket_id: int, data: TicketUpdate) -> TicketRead:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} not found")
        updated = await self.repo.update(ticket, data)
        return TicketRead.model_validate(updated)

    async def delete_ticket(self, ticket_id: int) -> None:
        ticket = await self.repo.get_by_id(ticket_id)
        if not ticket:
            raise TicketNotFoundError(f"Ticket #{ticket_id} not found")
        await self.repo.delete(ticket)

    async def get_stats(self) -> dict:
        return await self.repo.get_stats()
