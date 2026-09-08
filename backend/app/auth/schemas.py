"""Pydantic schemas for mocked OTP authentication."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class RegisterRequest(BaseModel):
    """Onboarding payload: identifier + profile + mocked OTP."""

    username: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=512)
    otp: str = Field(..., min_length=1, max_length=16)

    @field_validator("username", "phone", "avatar_url", mode="before")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _blank_to_none(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("display_name is required")
        return name

    @model_validator(mode="after")
    def require_username_or_phone(self) -> "RegisterRequest":
        if not self.username and not self.phone:
            raise ValueError("Provide a username or a phone number")
        return self


class LoginRequest(BaseModel):
    """Login with username or phone plus the mocked OTP."""

    username: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    otp: str = Field(..., min_length=1, max_length=16)

    @field_validator("username", "phone", mode="before")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def require_username_or_phone(self) -> "LoginRequest":
        if not self.username and not self.phone:
            raise ValueError("Provide a username or a phone number")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str | None
    phone: str | None
    display_name: str
    avatar_url: str | None
    bio: str | None
    is_online: bool
    last_seen: datetime | None
    created_at: datetime


class MessageOut(BaseModel):
    message: str
