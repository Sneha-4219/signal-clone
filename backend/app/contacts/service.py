"""Contact search, add, list, and remove operations."""

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Contact, User

SEARCH_LIMIT = 20


def search_users(db: Session, current_user: User, query: str) -> list[User]:
    term = (query or "").strip()
    if not term:
        return []
    pattern = f"%{term.lower()}%"
    stmt = (
        select(User)
        .where(
            User.id != current_user.id,
            or_(
                User.username.ilike(pattern),
                User.phone.ilike(pattern),
                User.display_name.ilike(pattern),
            ),
        )
        .order_by(User.display_name.asc())
        .limit(SEARCH_LIMIT)
    )
    return list(db.scalars(stmt))


def add_contact(db: Session, current_user: User, target_user_id: int) -> Contact:
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot add yourself as a contact",
        )
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    existing = db.scalar(
        select(Contact).where(
            Contact.user_id == current_user.id,
            Contact.contact_user_id == target_user_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact already exists",
        )
    contact = Contact(user_id=current_user.id, contact_user_id=target_user_id)
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact already exists",
        ) from None
    db.refresh(contact)
    contact.contact_user = target
    return contact


def list_contacts(db: Session, current_user: User) -> list[Contact]:
    stmt = (
        select(Contact)
        .options(selectinload(Contact.contact_user))
        .where(Contact.user_id == current_user.id)
        .join(User, User.id == Contact.contact_user_id)
        .order_by(User.display_name.asc())
    )
    return list(db.scalars(stmt).unique())


def remove_contact(db: Session, current_user: User, target_user_id: int) -> None:
    contact = db.scalar(
        select(Contact).where(
            Contact.user_id == current_user.id,
            Contact.contact_user_id == target_user_id,
        )
    )
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    db.delete(contact)
    db.commit()
