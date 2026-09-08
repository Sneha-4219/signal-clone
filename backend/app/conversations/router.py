"""HTTP routes for conversations. Messages are not returned in this stage."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.conversations.schemas import (
    AddGroupMemberRequest,
    ConversationOut,
    DirectConversationRequest,
    GroupConversationRequest,
    GroupMemberOut,
)
from app.conversations import service
from app.database import get_db
from app.models import User
from app.websocket.manager import manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_out(conversation, current_user_id: int) -> ConversationOut:
    payload = service.serialize_conversation(conversation, current_user_id)
    return ConversationOut.model_validate(payload)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConversationOut]:
    conversations = service.list_conversations(db, current_user)
    return [_to_out(item, current_user.id) for item in conversations]


@router.post("/direct", response_model=ConversationOut)
def create_direct_conversation(
    payload: DirectConversationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ConversationOut:
    conversation, created = service.create_direct_conversation(
        db, current_user, payload.target_user_id
    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return _to_out(conversation, current_user.id)


@router.post("/group", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_group_conversation(
    payload: GroupConversationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationOut:
    conversation = service.create_group_conversation(
        db, current_user, payload.name, payload.member_ids
    )
    return _to_out(conversation, current_user.id)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationOut:
    conversation = service.get_conversation(db, current_user, conversation_id)
    return _to_out(conversation, current_user.id)


def _member_out(member) -> GroupMemberOut:
    return GroupMemberOut.model_validate(service.serialize_group_member(member))


@router.get("/{conversation_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    conversation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GroupMemberOut]:
    members = service.list_group_members(db, current_user, conversation_id)
    return [_member_out(member) for member in members]


@router.post(
    "/{conversation_id}/members",
    response_model=GroupMemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_member(
    conversation_id: int,
    payload: AddGroupMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GroupMemberOut:
    member = service.add_group_member(
        db, current_user, conversation_id, payload.user_id
    )
    body = _member_out(member)
    await manager.broadcast(
        conversation_id,
        {
            "type": "group_member_added",
            "conversation_id": conversation_id,
            "user": {
                "user_id": body.user_id,
                "display_name": body.display_name,
                "role": body.role,
            },
        },
    )
    return body


@router.delete(
    "/{conversation_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_group_member(
    conversation_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    service.remove_group_member(db, current_user, conversation_id, user_id)
    sockets = manager.pop_user_from_conversation(conversation_id, user_id)
    await manager.broadcast(
        conversation_id,
        {
            "type": "group_member_removed",
            "conversation_id": conversation_id,
            "user_id": user_id,
        },
    )
    for socket in sockets:
        try:
            await socket.close(code=4403, reason="Removed from group")
        except Exception:
            pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)

