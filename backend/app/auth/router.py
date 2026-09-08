"""HTTP routes for mocked registration, login, current user, and logout."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginRequest, MessageOut, RegisterRequest, UserOut
from app.auth.service import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    get_valid_auth_session,
    login_user,
    register_user,
    set_session_cookie,
)
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user, auth_session = register_user(
        db,
        username=payload.username,
        phone=payload.phone,
        display_name=payload.display_name,
        avatar_url=payload.avatar_url,
        otp=payload.otp,
    )
    set_session_cookie(response, auth_session)
    return user


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user, auth_session = login_user(
        db,
        username=payload.username,
        phone=payload.phone,
        otp=payload.otp,
    )
    set_session_cookie(response, auth_session)
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/logout", response_model=MessageOut)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> MessageOut:
    auth_session = get_valid_auth_session(db, session_token)
    if auth_session is None:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    db.delete(auth_session)
    db.commit()
    clear_session_cookie(response)
    return MessageOut(message="Logged out")
