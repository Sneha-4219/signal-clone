"""Conversation request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contacts.schemas import PublicUserOut


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    role: str
    joined_at: datetime
    last_read_at: datetime | None
    user: PublicUserOut


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    members: list[MemberOut]
    other_user: PublicUserOut | None = None


class AddGroupMemberRequest(BaseModel):
    user_id: int = Field(..., gt=0)


class GroupMemberOut(BaseModel):
    user_id: int
    username: str | None
    display_name: str
    avatar_url: str | None
    role: str
    joined_at: datetime
    is_online: bool
    last_seen: datetime | None


class DirectConversationRequest(BaseModel):
    target_user_id: int = Field(..., gt=0)


class GroupConversationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    member_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Group name is required")
        return name
