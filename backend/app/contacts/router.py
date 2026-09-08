"""HTTP routes for contacts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.contacts.schemas import AddContactRequest, ContactOut, PublicUserOut
from app.contacts import service
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/search", response_model=list[PublicUserOut])
def search_contacts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    q: str = Query("", max_length=128),
) -> list[User]:
    return service.search_users(db, current_user, q)


@router.get("", response_model=list[ContactOut])
def list_contacts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ContactOut]:
    contacts = service.list_contacts(db, current_user)
    return [
        ContactOut(id=row.id, created_at=row.created_at, user=row.contact_user)
        for row in contacts
    ]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def add_contact(
    payload: AddContactRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ContactOut:
    contact = service.add_contact(db, current_user, payload.user_id)
    return ContactOut(
        id=contact.id,
        created_at=contact.created_at,
        user=contact.contact_user,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_contact(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.remove_contact(db, current_user, user_id)
