from datetime import datetime

from pydantic import BaseModel, EmailStr


class ContactBase(BaseModel):
    name: str
    mobile_number: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: str | None = None
    mobile_number: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ContactResponse(ContactBase):
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
