"""
Muteo Pydantic schemas — request/response models.
"""
from datetime import datetime

from pydantic import BaseModel, Field

__all__ = ["MuteoCreate", "MuteoRead"]


class MuteoCreate(BaseModel):
    """Schema for creating a new muteo record."""
    componente: str = Field(..., min_length=1, max_length=120, description="Component name")
    ticket: str = Field(..., min_length=1, max_length=120, description="Ticket reference")
    comentario: str = Field(..., min_length=1, max_length=5000, description="Comment/note")


class MuteoRead(BaseModel):
    """Schema for reading a muteo record."""
    id: int
    componente: str
    ticket: str
    comentario: str
    usuario: str
    created_at: datetime

    model_config = {"from_attributes": True}
