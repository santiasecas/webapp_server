"""
Pydantic schemas for Contact validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: Optional[str] = Field(None, max_length=30, description="Phone number")
    department: Optional[str] = Field(None, max_length=80, description="Department")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip()
        if cleaned and not all(c in "+0123456789 ()-." for c in cleaned):
            raise ValueError("Phone contains invalid characters")
        return cleaned or None

    @field_validator("department")
    @classmethod
    def department_strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else None


class ContactCreate(ContactBase):
    """Schema for creating a new contact."""
    pass


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact (all fields optional)."""
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, max_length=80)
    notes: Optional[str] = Field(None, max_length=2000)


class ContactRead(ContactBase):
    """Schema for reading a contact (includes DB-generated fields)."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ContactRead]
