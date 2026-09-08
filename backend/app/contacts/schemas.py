"""Public profile fields shared by contact and conversation APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    phone: str | None
    display_name: str
    avatar_url: str | None
    is_online: bool
    last_seen: datetime | None


class AddContactRequest(BaseModel):
    user_id: int = Field(..., gt=0)


class ContactOut(BaseModel):
    id: int
    created_at: datetime
    user: PublicUserOut
