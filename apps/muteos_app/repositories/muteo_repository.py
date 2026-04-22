"""
Muteo repository — data access layer.
"""
import logging
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.muteos_app.models import Muteo
from apps.muteos_app.schemas import MuteoCreate

logger = logging.getLogger(__name__)


class MuteoRepository:
    """Data access layer for Muteo records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 50,
        usuario: Optional[str] = None,
        componente: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Muteo], int]:
        """
        Retrieve all muteo records with optional filters.
        
        Args:
            page: Page number (1-indexed)
            page_size: Records per page
            usuario: Filter by user
            componente: Filter by component
            search: Search in componente, ticket, or comentario
            
        Returns:
            Tuple of (records, total_count)
        """
        query = select(Muteo)

        if usuario:
            query = query.where(Muteo.usuario == usuario)
        if componente:
            query = query.where(Muteo.componente.ilike(f"%{componente}%"))
        if search:
            term = f"%{search.lower()}%"
            query = query.where(
                (func.lower(Muteo.componente).like(term)) |
                (func.lower(Muteo.ticket).like(term)) |
                (func.lower(Muteo.comentario).like(term))
            )

        # Count total before pagination
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        # Apply ordering and pagination
        query = (
            query
            .order_by(desc(Muteo.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        result = await self.db.execute(query)
        records = result.scalars().all()
        return records, total

    async def get_by_id(self, muteo_id: int) -> Optional[Muteo]:
        """Get a single muteo record by ID."""
        result = await self.db.execute(
            select(Muteo).where(Muteo.id == muteo_id)
        )
        return result.scalars().first()

    async def create(self, data: MuteoCreate, usuario: str) -> Muteo:
        """Create a new muteo record."""
        muteo = Muteo(
            componente=data.componente,
            ticket=data.ticket,
            comentario=data.comentario,
            usuario=usuario,
        )
        self.db.add(muteo)
        await self.db.flush()
        await self.db.refresh(muteo)
        return muteo

    async def delete(self, muteo_id: int) -> bool:
        """Delete a muteo record by ID. Returns True if deleted, False if not found."""
        muteo = await self.get_by_id(muteo_id)
        if muteo:
            await self.db.delete(muteo)
            return True
        return False
