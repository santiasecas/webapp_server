"""
Muteo service — business logic layer.

Services coordinate repositories and apply business rules.
They are the layer between HTTP handlers and the database.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from apps.muteos_app.repositories import MuteoRepository
from apps.muteos_app.schemas import MuteoCreate, MuteoRead

logger = logging.getLogger(__name__)


class MuteoNotFoundError(Exception):
    """Raised when a muteo record is not found."""
    pass


class MuteoService:
    """Business logic for muteo operations."""

    def __init__(self, db: AsyncSession):
        self.repo = MuteoRepository(db)

    async def list_muteos(
        self,
        page: int = 1,
        page_size: int = 50,
        usuario: Optional[str] = None,
        componente: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[MuteoRead], int]:
        """
        List muteo records with optional filters.
        
        Returns:
            Tuple of (muteo_list, total_count)
        """
        muteos, total = await self.repo.get_all(
            page=page,
            page_size=page_size,
            usuario=usuario,
            componente=componente,
            search=search,
        )
        return [MuteoRead.model_validate(m) for m in muteos], total

    async def get_muteo(self, muteo_id: int) -> MuteoRead:
        """Get a single muteo by ID."""
        muteo = await self.repo.get_by_id(muteo_id)
        if not muteo:
            raise MuteoNotFoundError(f"Muteo #{muteo_id} not found")
        return MuteoRead.model_validate(muteo)

    async def create_muteo(self, data: MuteoCreate, usuario: str) -> MuteoRead:
        """Create a new muteo record."""
        muteo = await self.repo.create(data, usuario)
        return MuteoRead.model_validate(muteo)

    async def delete_muteo(self, muteo_id: int) -> None:
        """Delete a muteo record."""
        deleted = await self.repo.delete(muteo_id)
        if not deleted:
            raise MuteoNotFoundError(f"Muteo #{muteo_id} not found")
