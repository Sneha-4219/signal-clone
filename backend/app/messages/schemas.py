"""Request and response schemas for persistent messaging."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contacts.schemas import PublicUserOut

MAX_MESSAGE_LENGTH = 4000


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Message content cannot be empty")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ValueError("Message is too long")
        return text


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    status: str
    delivered_at: datetime | None
    read_at: datetime | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    status: str
    sender: PublicUserOut | None = None
    receipts: list[ReceiptOut] = Field(default_factory=list)


class MessageListOut(BaseModel):
    messages: list[MessageOut]
    limit: int
    offset: int
    total: int
