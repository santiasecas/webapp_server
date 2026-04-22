"""
Muteo model — SQLAlchemy ORM mapping.
Represents a mute/muting action on a ticket component.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Muteo(Base):
    __tablename__ = "muteos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    componente: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    ticket: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    usuario: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Muteo(id={self.id}, componente={self.componente}, ticket={self.ticket})>"
