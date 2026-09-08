"""Forward-only delivery/read transitions for message_receipts."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import utcnow
from app.conversations.service import get_conversation
from app.models import Message, MessageReceipt, User

_RANK = {"sent": 0, "delivered": 1, "read": 2}


def receipt_event(receipt: MessageReceipt) -> dict:
    return {
        "type": "receipt",
        "message_id": receipt.message_id,
        "user_id": receipt.user_id,
        "status": receipt.status,
        "delivered_at": receipt.delivered_at.isoformat() if receipt.delivered_at else None,
        "read_at": receipt.read_at.isoformat() if receipt.read_at else None,
    }


def _load_recipient_receipt(
    db: Session,
    current_user: User,
    message_id: int,
    conversation_id: int,
) -> MessageReceipt:
    get_conversation(db, current_user, conversation_id)
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    if message.sender_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senders cannot update recipient receipts",
        )
    receipt = db.scalar(
        select(MessageReceipt).where(
            MessageReceipt.message_id == message_id,
            MessageReceipt.user_id == current_user.id,
        )
    )
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )
    return receipt


def mark_message_delivered(
    db: Session,
    current_user: User,
    message_id: int,
    conversation_id: int,
) -> tuple[MessageReceipt, bool]:
    """Move sent → delivered. No-op if already delivered or read."""
    receipt = _load_recipient_receipt(db, current_user, message_id, conversation_id)
    if _RANK[receipt.status] >= _RANK["delivered"]:
        return receipt, False
    now = utcnow()
    receipt.status = "delivered"
    receipt.delivered_at = now
    db.commit()
    db.refresh(receipt)
    return receipt, True


def mark_message_read(
    db: Session,
    current_user: User,
    message_id: int,
    conversation_id: int,
) -> tuple[MessageReceipt, bool]:
    """Move sent/delivered → read. Sets delivered_at if it was missing."""
    receipt = _load_recipient_receipt(db, current_user, message_id, conversation_id)
    if receipt.status == "read":
        return receipt, False
    now = utcnow()
    if receipt.delivered_at is None:
        receipt.delivered_at = now
    receipt.status = "read"
    receipt.read_at = now
    db.commit()
    db.refresh(receipt)
    return receipt, True


def pending_sent_receipts(
    db: Session, current_user: User, conversation_id: int
) -> list[MessageReceipt]:
    """Recipient receipts still at sent for this conversation."""
    return list(
        db.scalars(
            select(MessageReceipt)
            .join(Message, Message.id == MessageReceipt.message_id)
            .where(
                MessageReceipt.user_id == current_user.id,
                MessageReceipt.status == "sent",
                Message.conversation_id == conversation_id,
                Message.sender_id != current_user.id,
            )
        )
    )
