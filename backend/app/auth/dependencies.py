"""Reusable authentication dependency for current-user lookups."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.service import SESSION_COOKIE_NAME, get_valid_auth_session
from app.database import get_db
from app.models import User


def load_user_from_session_token(db: Session, session_token: str | None) -> User:
    """Resolve a user from the database-backed session cookie value."""
    auth_session = get_valid_auth_session(db, session_token)
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.get(User, auth_session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    """Load the authenticated user from the HTTP-only session cookie."""
    return load_user_from_session_token(db, session_token)
