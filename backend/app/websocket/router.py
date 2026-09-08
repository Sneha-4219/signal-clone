"""Authenticated WebSocket transport for conversation messages."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.auth.dependencies import load_user_from_session_token
from app.auth.service import SESSION_COOKIE_NAME
from app.conversations.service import get_conversation
from app.database import get_db
from app.messages import receipts as receipts_service
from app.messages import service as messages_service
from app.messages.schemas import MessageOut, ReceiptOut
from app.models import Message, User
from app.websocket import presence as presence_service
from app.websocket.manager import manager

router = APIRouter(tags=["websocket"])

_CLOSE_UNAUTHENTICATED = 4401
_CLOSE_FORBIDDEN = 4403
_CLOSE_NOT_FOUND = 4404


def _message_payload(message: Message) -> dict:
    body = MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        content=message.content,
        created_at=message.created_at,
        updated_at=message.updated_at,
        status=messages_service.message_status(message),
        sender=message.sender,
        receipts=[ReceiptOut.model_validate(row) for row in message.receipts],
    )
    return body.model_dump(mode="json")


def _close_code_for(exc: HTTPException) -> int:
    if exc.status_code == 401:
        return _CLOSE_UNAUTHENTICATED
    if exc.status_code == 403:
        return _CLOSE_FORBIDDEN
    if exc.status_code == 404:
        return _CLOSE_NOT_FOUND
    return 1008


async def _safe_close(websocket: WebSocket, code: int, reason: str) -> None:
    if websocket.client_state == WebSocketState.DISCONNECTED:
        return
    await websocket.close(code=code, reason=reason[:120])


async def _deliver_to_connected_recipients(
    db: Session, conversation_id: int, sender_id: int, message_id: int
) -> None:
    for user_id in manager.user_ids(conversation_id):
        if user_id == sender_id:
            continue
        recipient = db.get(User, user_id)
        if recipient is None:
            continue
        receipt, changed = receipts_service.mark_message_delivered(
            db, recipient, message_id, conversation_id
        )
        if changed:
            await manager.broadcast(conversation_id, receipts_service.receipt_event(receipt))


async def _catch_up_deliveries(
    db: Session, user: User, conversation_id: int
) -> None:
    pending = receipts_service.pending_sent_receipts(db, user, conversation_id)
    for pending_receipt in pending:
        try:
            receipt, changed = receipts_service.mark_message_delivered(
                db, user, pending_receipt.message_id, conversation_id
            )
        except HTTPException:
            continue
        if changed:
            await manager.broadcast(conversation_id, receipts_service.receipt_event(receipt))


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_socket(
    websocket: WebSocket,
    conversation_id: int,
    db: Session = Depends(get_db),
) -> None:
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    try:
        user = load_user_from_session_token(db, token)
        get_conversation(db, user, conversation_id)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail if isinstance(exc.detail, str) else "Forbidden"
        await _safe_close(websocket, _close_code_for(exc), detail)
        return

    await websocket.accept()
    coming_online = manager.user_connection_count(user.id) == 0
    manager.connect(conversation_id, user.id, websocket)
    try:
        if coming_online:
            user = presence_service.mark_user_online(db, user)
            await manager.broadcast_to_others(
                conversation_id, user.id, presence_service.presence_event(user)
            )
        await _catch_up_deliveries(db, user, conversation_id)
        db.commit()
        while True:
            raw = await websocket.receive_text()
            await _handle_client_event(websocket, db, user, conversation_id, raw)
    except WebSocketDisconnect:
        pass
    finally:
        await _cleanup_socket(db, user, conversation_id, websocket)


async def _handle_client_event(
    websocket: WebSocket,
    db: Session,
    user: User,
    conversation_id: int,
    raw: str,
) -> None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
        return
    if not isinstance(payload, dict):
        await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
        return

    event_type = payload.get("type")
    if event_type == "read":
        await _handle_read_event(websocket, db, user, conversation_id, payload)
        return
    if event_type == "typing":
        await _handle_typing_event(websocket, user, conversation_id, payload)
        return
    if event_type != "message":
        await websocket.send_json({"type": "error", "detail": "Unsupported event type"})
        return

    content = payload.get("content")
    if not isinstance(content, str):
        await websocket.send_json({"type": "error", "detail": "Invalid message content"})
        return
    try:
        message = messages_service.send_message(db, user, conversation_id, content)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Invalid message"
        await websocket.send_json(
            {"type": "error", "detail": detail, "status": exc.status_code}
        )
        return

    await manager.broadcast(
        conversation_id,
        {"type": "message", "message": _message_payload(message)},
    )
    await _deliver_to_connected_recipients(
        db, conversation_id, user.id, message.id
    )


async def _handle_read_event(
    websocket: WebSocket,
    db: Session,
    user: User,
    conversation_id: int,
    payload: dict,
) -> None:
    message_id = payload.get("message_id")
    if not isinstance(message_id, int):
        await websocket.send_json({"type": "error", "detail": "Invalid message_id"})
        return
    try:
        receipt, _changed = receipts_service.mark_message_read(
            db, user, message_id, conversation_id
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Cannot mark read"
        await websocket.send_json(
            {"type": "error", "detail": detail, "status": exc.status_code}
        )
        return
    await manager.broadcast(conversation_id, receipts_service.receipt_event(receipt))


async def _handle_typing_event(
    websocket: WebSocket,
    user: User,
    conversation_id: int,
    payload: dict,
) -> None:
    is_typing = payload.get("is_typing")
    if not isinstance(is_typing, bool):
        await websocket.send_json(
            {"type": "error", "detail": "is_typing must be a boolean"}
        )
        return
    manager.set_typing(conversation_id, user.id, is_typing)
    await manager.broadcast_to_others(
        conversation_id,
        user.id,
        {"type": "typing", "user_id": user.id, "is_typing": is_typing},
    )


async def _cleanup_socket(
    db: Session, user: User, conversation_id: int, websocket: WebSocket
) -> None:
    shared_conversations = manager.conversation_ids_for_user(user.id)
    manager.disconnect(websocket)
    try:
        if user.id not in manager.user_ids(conversation_id):
            was_typing = manager.clear_typing(conversation_id, user.id)
            if was_typing and manager.user_ids(conversation_id):
                await manager.broadcast_to_others(
                    conversation_id,
                    user.id,
                    {"type": "typing", "user_id": user.id, "is_typing": False},
                )
    except Exception:
        pass
    if manager.user_connection_count(user.id) != 0:
        return
    try:
        user = presence_service.mark_user_offline(db, user)
        for shared_id in shared_conversations:
            await manager.broadcast(shared_id, presence_service.presence_event(user))
    except Exception:
        return

