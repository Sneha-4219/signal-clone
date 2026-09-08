"""Persist online / last-seen from WebSocket connection lifetime."""

from app.auth.service import utcnow
from app.models import User
from sqlalchemy.orm import Session


def presence_event(user: User) -> dict:
    return {
        "type": "presence",
        "user_id": user.id,
        "is_online": user.is_online,
        "last_seen": user.last_seen.isoformat() if user.last_seen else None,
    }


def mark_user_online(db: Session, user: User) -> User:
    row = db.get(User, user.id) or user
    row.is_online = True
    db.commit()
    db.refresh(row)
    return row


def mark_user_offline(db: Session, user: User) -> User:
    row = db.get(User, user.id) or user
    row.is_online = False
    row.last_seen = utcnow()
    db.commit()
    db.refresh(row)
    return row
