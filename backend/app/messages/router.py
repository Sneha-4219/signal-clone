"""REST routes for conversation messages."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.messages import receipts as receipts_service
from app.messages.schemas import MessageListOut, MessageOut, ReceiptOut, SendMessageRequest
from app.messages import service
from app.models import Message, User
from app.websocket.manager import manager

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages",
    tags=["messages"],
)


def _to_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        content=message.content,
        created_at=message.created_at,
        updated_at=message.updated_at,
        status=service.message_status(message),
        sender=message.sender,
        receipts=[ReceiptOut.model_validate(row) for row in message.receipts],
    )


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageOut:
    message = service.send_message(
        db, current_user, conversation_id, payload.content
    )
    body = _to_out(message)
    await manager.broadcast(
        conversation_id,
        {"type": "message", "message": body.model_dump(mode="json")},
    )
    for user_id in manager.user_ids(conversation_id):
        if user_id == current_user.id:
            continue
        recipient = db.get(User, user_id)
        if recipient is None:
            continue
        receipt, changed = receipts_service.mark_message_delivered(
            db, recipient, message.id, conversation_id
        )
        if changed:
            await manager.broadcast(
                conversation_id, receipts_service.receipt_event(receipt)
            )
    return body


@router.get("", response_model=MessageListOut)
def list_messages(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(service.DEFAULT_PAGE_LIMIT, ge=1, le=service.MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
) -> MessageListOut:
    rows, total = service.list_messages(
        db, current_user, conversation_id, limit=limit, offset=offset
    )
    return MessageListOut(
        messages=[_to_out(row) for row in rows],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.post("/{message_id}/read", response_model=ReceiptOut)
async def mark_message_read(
    conversation_id: int,
    message_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReceiptOut:
    receipt, _changed = receipts_service.mark_message_read(
        db, current_user, message_id, conversation_id
    )
    await manager.broadcast(conversation_id, receipts_service.receipt_event(receipt))
    return ReceiptOut.model_validate(receipt)
