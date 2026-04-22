"""
Ticket Pydantic schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from apps.tickets_app.models import TicketPriority, TicketStatus

# Re-export enums so templates/routers don't need to import models
__all__ = ["TicketCreate", "TicketUpdate", "TicketRead", "TicketStatus", "TicketPriority"]


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    priority: TicketPriority = TicketPriority.medium
    assigned_to: Optional[str] = Field(None, max_length=80)
    reporter: str = Field(..., min_length=1, max_length=80)


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[str] = Field(None, max_length=80)


class TicketRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: TicketStatus
    priority: TicketPriority
    assigned_to: Optional[str]
    reporter: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Human-readable labels for templates
STATUS_LABELS = {
    TicketStatus.open:        ("Open",        "badge-blue"),
    TicketStatus.in_progress: ("In Progress", "badge-yellow"),
    TicketStatus.resolved:    ("Resolved",    "badge-green"),
    TicketStatus.closed:      ("Closed",      "badge-gray"),
}

PRIORITY_LABELS = {
    TicketPriority.low:    ("Low",    "badge-gray"),
    TicketPriority.medium: ("Medium", "badge-blue"),
    TicketPriority.high:   ("High",   "badge-orange"),
    TicketPriority.urgent: ("Urgent", "badge-red"),
}
