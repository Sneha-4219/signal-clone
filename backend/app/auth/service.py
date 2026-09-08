"""Mocked OTP checks, session tokens, and HTTP-only cookies.

This is not real Signal authentication: OTP is a fixed development value,
there is no SMS, and there is no cryptographic key exchange.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuthSession, User

# Mocked development OTP — not delivered over SMS.
FIXED_OTP = "123456"

SESSION_COOKIE_NAME = "session_token"
SESSION_TTL = timedelta(days=30)

_ALLOWED_AVATAR_PREFIXES = ("http://", "https://", "/", "data:image/")


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the existing SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def verify_otp(otp: str) -> None:
    provided = (otp or "").strip()
    expected = FIXED_OTP
    if len(provided) != len(expected) or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")


def validate_avatar_url(avatar_url: str | None) -> str | None:
    if avatar_url is None:
        return None
    if len(avatar_url) > 512:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="avatar_url is too long",
        )
    if not avatar_url.startswith(_ALLOWED_AVATAR_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="avatar_url must be an http(s) URL, a site path, or a data:image URI",
        )
    return avatar_url


def create_auth_session(db: Session, user: User) -> AuthSession:
    session = AuthSession(
        user_id=user.id,
        session_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + SESSION_TTL,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def set_session_cookie(response: Response, auth_session: AuthSession) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=auth_session.session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=int(SESSION_TTL.total_seconds()),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def get_valid_auth_session(db: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.session_token == token)
    )
    if auth_session is None:
        return None
    if auth_session.expires_at <= utcnow():
        db.delete(auth_session)
        db.commit()
        return None
    return auth_session


def register_user(
    db: Session,
    *,
    username: str | None,
    phone: str | None,
    display_name: str,
    avatar_url: str | None,
    otp: str,
) -> tuple[User, AuthSession]:
    verify_otp(otp)
    avatar_url = validate_avatar_url(avatar_url)

    if username:
        taken = db.scalar(select(User).where(User.username == username))
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
    if phone:
        taken = db.scalar(select(User).where(User.phone == phone))
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already taken",
            )

    user = User(
        username=username,
        phone=phone,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or phone number already taken",
        ) from None
    db.refresh(user)
    return user, create_auth_session(db, user)


def login_user(
    db: Session,
    *,
    username: str | None,
    phone: str | None,
    otp: str,
) -> tuple[User, AuthSession]:
    verify_otp(otp)

    if username and phone:
        user = db.scalar(
            select(User).where(User.username == username, User.phone == phone)
        )
    elif username:
        user = db.scalar(select(User).where(User.username == username))
    else:
        user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user, create_auth_session(db, user)
