"""
Webapp permissions model — controls user access to webapps.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class WebappPermission(Base):
    """
    Tracks which users have access to which webapps.
    
    Each record represents a user having been granted access to a webapp.
    If a user is in the "admins" group, they have access to all webapps
    regardless of this table (see permissions logic).
    """
    __tablename__ = "webapp_permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    webapp_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Prevent duplicate permissions for the same user+webapp
    __table_args__ = (
        UniqueConstraint("username", "webapp_id", name="uk_username_webapp"),
    )

    def __repr__(self) -> str:
        return f"<WebappPermission(username={self.username}, webapp_id={self.webapp_id})>"
