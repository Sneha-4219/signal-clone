"""Persist messages and initial sent receipts. No real-time delivery yet."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.service import utcnow
from app.conversations.service import get_conversation
from app.messages.schemas import MAX_MESSAGE_LENGTH
from app.models import Message, MessageReceipt, User

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100


def normalize_content(content: str) -> str:
    text = (content or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )
    if len(text) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is too long",
        )
    return text


def _load_message(db: Session, message_id: int) -> Message | None:
    return db.scalar(
        select(Message)
        .options(
            selectinload(Message.receipts),
            selectinload(Message.sender),
        )
        .where(Message.id == message_id)
    )


def send_message(
    db: Session, current_user: User, conversation_id: int, content: str
) -> Message:
    """Persist a message, bump conversation activity, and create recipient receipts."""
    conversation = get_conversation(db, current_user, conversation_id)
    text = normalize_content(content)
    sent_at = utcnow()

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=text,
        created_at=sent_at,
        updated_at=sent_at,
    )
    conversation.updated_at = sent_at

    for member in conversation.members:
        if member.user_id == current_user.id:
            continue
        message.receipts.append(
            MessageReceipt(user_id=member.user_id, status="sent")
        )

    db.add(message)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not send message",
        ) from None

    loaded = _load_message(db, message.id)
    return loaded or message


def list_messages(
    db: Session,
    current_user: User,
    conversation_id: int,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
) -> tuple[list[Message], int]:
    get_conversation(db, current_user, conversation_id)
    if limit < 1 or limit > MAX_PAGE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 100",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must be >= 0",
        )

    total = db.scalar(
        select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )
    ) or 0
    rows = list(
        db.scalars(
            select(Message)
            .options(
                selectinload(Message.receipts),
                selectinload(Message.sender),
            )
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return rows, total


def message_status(message: Message) -> str:
    """Sender-facing aggregate of recipient receipts (forward-only ranks)."""
    receipts = list(message.receipts or [])
    if not receipts:
        return "sent"
    rank = {"sent": 0, "delivered": 1, "read": 2}
    best = "sent"
    for receipt in receipts:
        if rank.get(receipt.status, 0) > rank.get(best, 0):
            best = receipt.status
    return best
