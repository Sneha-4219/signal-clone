"""Development sample data for the Signal Clone API.

Run explicitly from the backend directory:

    python -m app.seed

This module is not imported by FastAPI startup.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import (
    Contact,
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
    User,
)

# Stable fictional timestamps so re-runs match existing seed rows.
SEED_EPOCH = datetime(2026, 9, 1, 9, 0, 0)

SAMPLE_USERS = [
    {
        "username": "sneha",
        "phone": "+15550001001",
        "display_name": "Sneha",
        "avatar_url": "https://ui-avatars.com/api/?name=Sneha&background=3A76F0&color=fff",
        "bio": "Building the Signal Clone assignment.",
        "is_online": True,
        "last_seen": None,
    },
    {
        "username": "rahul",
        "phone": "+15550001002",
        "display_name": "Rahul",
        "avatar_url": "https://ui-avatars.com/api/?name=Rahul&background=2C6E49&color=fff",
        "bio": "Backend stand-in teammate for local demos.",
        "is_online": False,
        "last_seen": SEED_EPOCH + timedelta(hours=8, minutes=12),
    },
    {
        "username": "priya",
        "phone": "+15550001003",
        "display_name": "Priya",
        "avatar_url": "https://ui-avatars.com/api/?name=Priya&background=9B5DE5&color=fff",
        "bio": "Designs the chat list and composer.",
        "is_online": True,
        "last_seen": None,
    },
    {
        "username": "amit",
        "phone": "+15550001004",
        "display_name": "Amit",
        "avatar_url": "https://ui-avatars.com/api/?name=Amit&background=F77F00&color=fff",
        "bio": "Asks about tests until they pass.",
        "is_online": False,
        "last_seen": SEED_EPOCH + timedelta(hours=6, minutes=40),
    },
    {
        "username": "neha",
        "phone": "+15550001005",
        "display_name": "Neha",
        "avatar_url": "https://ui-avatars.com/api/?name=Neha&background=D62828&color=fff",
        "bio": "Weekend plans and group-chat energy.",
        "is_online": False,
        "last_seen": SEED_EPOCH + timedelta(hours=10, minutes=5),
    },
]

CONTACT_PAIRS = [
    ("sneha", "rahul"),
    ("sneha", "priya"),
    ("sneha", "amit"),
    ("sneha", "neha"),
    ("rahul", "sneha"),
    ("rahul", "priya"),
    ("rahul", "amit"),
    ("priya", "sneha"),
    ("priya", "rahul"),
    ("amit", "sneha"),
    ("amit", "rahul"),
    ("neha", "sneha"),
]

DIRECT_PAIRS = [
    ("sneha", "rahul"),
    ("sneha", "priya"),
    ("sneha", "amit"),
    ("sneha", "neha"),
    ("rahul", "amit"),
]

GROUPS = [
    {
        "name": "Project Team",
        "creator": "sneha",
        "members": ["sneha", "rahul", "priya", "amit"],
    },
    {
        "name": "Weekend Plans",
        "creator": "sneha",
        "members": ["sneha", "priya", "neha"],
    },
]


def get_or_create_user(db: Session, spec: dict) -> User:
    user = db.scalar(select(User).where(User.username == spec["username"]))
    if user is not None:
        return user
    user = User(**spec)
    db.add(user)
    db.flush()
    return user


def get_or_create_contact(db: Session, owner: User, other: User) -> Contact:
    row = db.scalar(
        select(Contact).where(
            Contact.user_id == owner.id,
            Contact.contact_user_id == other.id,
        )
    )
    if row is not None:
        return row
    row = Contact(user_id=owner.id, contact_user_id=other.id)
    db.add(row)
    db.flush()
    return row


def get_or_create_direct_conversation(
    db: Session, user_a: User, user_b: User
) -> Conversation:
    pair_key = Conversation.make_direct_pair_key(user_a.id, user_b.id)
    conversation = db.scalar(
        select(Conversation).where(Conversation.direct_pair_key == pair_key)
    )
    if conversation is not None:
        return conversation
    conversation = Conversation(
        type="direct",
        name=None,
        direct_pair_key=pair_key,
        created_by=user_a.id,
        created_at=SEED_EPOCH,
        updated_at=SEED_EPOCH,
    )
    conversation.members.append(
        ConversationMember(user_id=user_a.id, role="member", joined_at=SEED_EPOCH)
    )
    conversation.members.append(
        ConversationMember(user_id=user_b.id, role="member", joined_at=SEED_EPOCH)
    )
    db.add(conversation)
    db.flush()
    return conversation


def get_or_create_group(
    db: Session, name: str, creator: User, members: list[User]
) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.type == "group",
            Conversation.name == name,
        )
    )
    if conversation is None:
        conversation = Conversation(
            type="group",
            name=name,
            direct_pair_key=None,
            created_by=creator.id,
            created_at=SEED_EPOCH + timedelta(hours=1),
            updated_at=SEED_EPOCH + timedelta(hours=1),
        )
        db.add(conversation)
        db.flush()

    existing_ids = {
        row.user_id
        for row in db.scalars(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation.id
            )
        )
    }
    for user in members:
        if user.id in existing_ids:
            continue
        role = "admin" if user.id == creator.id else "member"
        db.add(
            ConversationMember(
                conversation_id=conversation.id,
                user_id=user.id,
                role=role,
                joined_at=SEED_EPOCH + timedelta(hours=1),
            )
        )
    db.flush()
    return conversation


def _member_ids(db: Session, conversation: Conversation) -> list[int]:
    return list(
        db.scalars(
            select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conversation.id
            )
        )
    )


def create_sample_message(
    db: Session,
    conversation: Conversation,
    sender: User,
    content: str,
    created_at: datetime,
    recipient_statuses: dict[int, str],
) -> Message:
    existing = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sender_id == sender.id,
            Message.content == content,
        )
    )
    if existing is not None:
        return existing

    message = Message(
        conversation_id=conversation.id,
        sender_id=sender.id,
        content=content,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(message)
    db.flush()

    for user_id, receipt_status in recipient_statuses.items():
        if user_id == sender.id:
            continue
        delivered_at = None
        read_at = None
        if receipt_status in {"delivered", "read"}:
            delivered_at = created_at + timedelta(minutes=2)
        if receipt_status == "read":
            read_at = created_at + timedelta(minutes=8)
        db.add(
            MessageReceipt(
                message_id=message.id,
                user_id=user_id,
                status=receipt_status,
                delivered_at=delivered_at,
                read_at=read_at,
            )
        )
    db.flush()
    return message


def _receipts_for_others(
    member_ids: list[int], sender_id: int, pattern: list[str]
) -> dict[int, str]:
    others = [user_id for user_id in member_ids if user_id != sender_id]
    statuses: dict[int, str] = {}
    for index, user_id in enumerate(others):
        statuses[user_id] = pattern[index % len(pattern)]
    return statuses


def _touch_conversation(db: Session, conversation: Conversation) -> None:
    latest = db.scalar(
        select(Message.created_at)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if latest is not None:
        conversation.updated_at = latest


def seed(db: Session) -> dict[str, int]:
    users = {spec["username"]: get_or_create_user(db, spec) for spec in SAMPLE_USERS}
    db.flush()

    contacts = [
        get_or_create_contact(db, users[owner], users[other])
        for owner, other in CONTACT_PAIRS
    ]

    directs = [
        get_or_create_direct_conversation(db, users[left], users[right])
        for left, right in DIRECT_PAIRS
    ]

    groups = [
        get_or_create_group(
            db,
            spec["name"],
            users[spec["creator"]],
            [users[name] for name in spec["members"]],
        )
        for spec in GROUPS
    ]

    sneha, rahul, priya, amit, neha = (
        users["sneha"],
        users["rahul"],
        users["priya"],
        users["amit"],
        users["neha"],
    )
    sneha_rahul, sneha_priya, sneha_amit, sneha_neha, rahul_amit = directs
    project_team, weekend_plans = groups

    sample_threads: list[tuple[Conversation, list[tuple[User, str, datetime, list[str]]]]] = [
        (
            sneha_rahul,
            [
                (rahul, "Hey Sneha, did you finish the API?", SEED_EPOCH + timedelta(hours=2), ["read"]),
                (sneha, "Almost. I'm testing the messaging flow now.", SEED_EPOCH + timedelta(hours=2, minutes=4), ["read"]),
                (rahul, "Nice! Let me know when it's ready.", SEED_EPOCH + timedelta(hours=2, minutes=7), ["delivered"]),
                (sneha, "Will do. Direct chats look good so far.", SEED_EPOCH + timedelta(hours=2, minutes=12), ["sent"]),
            ],
        ),
        (
            sneha_priya,
            [
                (priya, "Can you review the conversation list layout?", SEED_EPOCH + timedelta(hours=3), ["read"]),
                (sneha, "Yes — I'll check it after the seed data is in.", SEED_EPOCH + timedelta(hours=3, minutes=6), ["read"]),
                (priya, "Thanks. I'll polish the avatars in the meantime.", SEED_EPOCH + timedelta(hours=3, minutes=15), ["delivered"]),
            ],
        ),
        (
            sneha_amit,
            [
                (amit, "Are the unit tests still green?", SEED_EPOCH + timedelta(hours=4), ["read"]),
                (sneha, "They were this morning. I'll re-run after seeding.", SEED_EPOCH + timedelta(hours=4, minutes=3), ["sent"]),
            ],
        ),
        (
            sneha_neha,
            [
                (neha, "Coffee this weekend?", SEED_EPOCH + timedelta(hours=5), ["read"]),
                (sneha, "Yes, Saturday afternoon works.", SEED_EPOCH + timedelta(hours=5, minutes=10), ["delivered"]),
            ],
        ),
        (
            rahul_amit,
            [
                (rahul, "I'll pair with you on pagination next.", SEED_EPOCH + timedelta(hours=4, minutes=30), ["read"]),
                (amit, "Perfect. I'll stub the limit/offset cases.", SEED_EPOCH + timedelta(hours=4, minutes=34), ["sent"]),
            ],
        ),
        (
            project_team,
            [
                (sneha, "Project Team is our sample group for the assignment demo.", SEED_EPOCH + timedelta(hours=6), ["read", "read", "delivered"]),
                (rahul, "I'll drop API notes here as we go.", SEED_EPOCH + timedelta(hours=6, minutes=8), ["read", "delivered", "sent"]),
                (priya, "Composer and receipts can wait until WebSockets.", SEED_EPOCH + timedelta(hours=6, minutes=14), ["delivered", "sent", "sent"]),
                (amit, "I'll keep the test count honest.", SEED_EPOCH + timedelta(hours=6, minutes=20), ["sent", "sent", "sent"]),
            ],
        ),
        (
            weekend_plans,
            [
                (neha, "Board game night at 7?", SEED_EPOCH + timedelta(hours=7), ["read", "delivered"]),
                (priya, "I'm in. I'll bring snacks.", SEED_EPOCH + timedelta(hours=7, minutes=9), ["read", "sent"]),
            ],
        ),
    ]

    messages: list[Message] = []
    for conversation, thread in sample_threads:
        member_ids = _member_ids(db, conversation)
        for sender, content, created_at, pattern in thread:
            statuses = _receipts_for_others(member_ids, sender.id, pattern)
            messages.append(
                create_sample_message(
                    db, conversation, sender, content, created_at, statuses
                )
            )
        _touch_conversation(db, conversation)

    message_ids = [message.id for message in messages]
    receipts = []
    if message_ids:
        receipts = list(
            db.scalars(
                select(MessageReceipt).where(MessageReceipt.message_id.in_(message_ids))
            )
        )

    return {
        "users": len(users),
        "contacts": len(contacts),
        "direct_conversations": len(directs),
        "groups": len(groups),
        "messages": len(messages),
        "receipts": len(receipts),
    }


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        summary = seed(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Seed complete:")
    print(f"- Users: {summary['users']}")
    print(f"- Contacts: {summary['contacts']}")
    print(f"- Direct conversations: {summary['direct_conversations']}")
    print(f"- Groups: {summary['groups']}")
    print(f"- Messages: {summary['messages']}")
    print(f"- Receipts: {summary['receipts']}")
    print("Log in with any seeded username and OTP 123456.")


if __name__ == "__main__":
    main()
