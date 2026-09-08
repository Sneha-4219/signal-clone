"""Conversation list, lookup, and creation (no messaging)."""

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.service import utcnow
from app.models import Conversation, ConversationMember, Message, User


def touch_conversation(conversation: Conversation) -> None:
    """Bump activity time. Messaging should call this when a message is stored."""
    conversation.updated_at = utcnow()


def _member_user_ids(conversation: Conversation) -> set[int]:
    return {member.user_id for member in conversation.members}


def other_user(conversation: Conversation, current_user_id: int) -> User | None:
    if conversation.type != "direct":
        return None
    for member in conversation.members:
        if member.user_id != current_user_id:
            return member.user
    return None


def serialize_conversation(
    conversation: Conversation, current_user_id: int
) -> dict:
    return {
        "id": conversation.id,
        "type": conversation.type,
        "name": conversation.name,
        "created_by": conversation.created_by,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "members": conversation.members,
        "other_user": other_user(conversation, current_user_id),
    }


def _load_conversation(db: Session, conversation_id: int) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .where(Conversation.id == conversation_id)
    )


def list_conversations(db: Session, current_user: User) -> list[Conversation]:
    last_message_at = (
        select(func.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    activity_at = func.coalesce(
        last_message_at,
        Conversation.updated_at,
        Conversation.created_at,
    )
    stmt = (
        select(Conversation)
        .join(ConversationMember)
        .where(ConversationMember.user_id == current_user.id)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .order_by(activity_at.desc(), Conversation.id.desc())
    )
    return list(db.scalars(stmt).unique())


def get_conversation(
    db: Session, current_user: User, conversation_id: int
) -> Conversation:
    conversation = _load_conversation(db, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    if current_user.id not in _member_user_ids(conversation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this conversation",
        )
    return conversation


def _add_members(
    conversation: Conversation,
    user_roles: Iterable[tuple[User, str]],
) -> None:
    for user, role in user_roles:
        conversation.members.append(
            ConversationMember(user_id=user.id, role=role, user=user)
        )


def create_direct_conversation(
    db: Session, current_user: User, target_user_id: int
) -> tuple[Conversation, bool]:
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a direct conversation with yourself",
        )
    target = db.get(User, target_user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    pair_key = Conversation.make_direct_pair_key(current_user.id, target_user_id)
    existing = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .where(Conversation.direct_pair_key == pair_key)
    )
    if existing is not None:
        return existing, False

    conversation = Conversation(
        type="direct",
        name=None,
        direct_pair_key=pair_key,
        created_by=current_user.id,
    )
    _add_members(
        conversation,
        ((current_user, "member"), (target, "member")),
    )
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.direct_pair_key == pair_key)
        )
        if existing is not None:
            return existing, False
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Direct conversation already exists",
        ) from None
    db.refresh(conversation)
    loaded = _load_conversation(db, conversation.id) or conversation
    return loaded, True


def create_group_conversation(
    db: Session,
    current_user: User,
    name: str,
    member_ids: list[int],
) -> Conversation:
    unique_ids: list[int] = []
    seen: set[int] = set()
    for user_id in member_ids:
        if user_id not in seen:
            seen.add(user_id)
            unique_ids.append(user_id)

    extra_ids = [user_id for user_id in unique_ids if user_id != current_user.id]
    extra_users: list[User] = []
    if extra_ids:
        extra_users = list(db.scalars(select(User).where(User.id.in_(extra_ids))))
        found_ids = {user.id for user in extra_users}
        missing = [user_id for user_id in extra_ids if user_id not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more member IDs are invalid",
            )

    conversation = Conversation(
        type="group",
        name=name,
        direct_pair_key=None,
        created_by=current_user.id,
    )
    roles: list[tuple[User, str]] = [(current_user, "admin")]
    roles.extend((user, "member") for user in extra_users)
    _add_members(conversation, roles)
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create group conversation",
        ) from None
    db.refresh(conversation)
    return _load_conversation(db, conversation.id) or conversation


def _membership(conversation: Conversation, user_id: int) -> ConversationMember | None:
    for member in conversation.members:
        if member.user_id == user_id:
            return member
    return None


def _require_group(conversation: Conversation) -> None:
    if conversation.type != "group":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group management is only available for group conversations",
        )


def serialize_group_member(member: ConversationMember) -> dict:
    user = member.user
    return {
        "user_id": member.user_id,
        "username": user.username if user is not None else None,
        "display_name": user.display_name if user is not None else "",
        "avatar_url": user.avatar_url if user is not None else None,
        "role": member.role,
        "joined_at": member.joined_at,
        "is_online": bool(user.is_online) if user is not None else False,
        "last_seen": user.last_seen if user is not None else None,
    }


def list_group_members(
    db: Session, current_user: User, conversation_id: int
) -> list[ConversationMember]:
    conversation = get_conversation(db, current_user, conversation_id)
    _require_group(conversation)
    return sorted(conversation.members, key=lambda row: (row.joined_at, row.user_id))


def add_group_member(
    db: Session, current_user: User, conversation_id: int, user_id: int
) -> ConversationMember:
    conversation = get_conversation(db, current_user, conversation_id)
    _require_group(conversation)
    actor = _membership(conversation, current_user.id)
    if actor is None or actor.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a group admin can add members",
        )
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if _membership(conversation, user_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this group",
        )
    member = ConversationMember(
        conversation_id=conversation.id,
        user_id=target.id,
        role="member",
        joined_at=utcnow(),
        user=target,
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this group",
        ) from None
    db.refresh(member)
    db.refresh(target)
    member.user = target
    return member


def remove_group_member(
    db: Session, current_user: User, conversation_id: int, user_id: int
) -> None:
    conversation = get_conversation(db, current_user, conversation_id)
    _require_group(conversation)
    actor = _membership(conversation, current_user.id)
    target = _membership(conversation, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    leaving_self = user_id == current_user.id
    if not leaving_self and (actor is None or actor.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a group admin can remove members",
        )
    admin_count = sum(1 for member in conversation.members if member.role == "admin")
    if target.role == "admin" and admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last group admin.",
        )
    db.delete(target)
    db.commit()

