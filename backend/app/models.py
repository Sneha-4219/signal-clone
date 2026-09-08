"""SQLAlchemy models for the Signal Clone database schema."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A registered (or later mocked) messaging user."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_is_online", "is_online"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    bio: Mapped[str | None] = mapped_column(Text)
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="user",
        foreign_keys="Contact.user_id",
        cascade="all, delete-orphan",
    )
    contacted_by: Mapped[list["Contact"]] = relationship(
        back_populates="contact_user",
        foreign_keys="Contact.contact_user_id",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[list["ConversationMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="creator",
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        back_populates="sender",
    )
    message_receipts: Mapped[list["MessageReceipt"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Contact(Base):
    """One-way address-book relationship from a user to another user."""

    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("user_id", "contact_user_id", name="uq_contacts_user_contact"),
        CheckConstraint("user_id != contact_user_id", name="ck_contacts_no_self"),
        Index("ix_contacts_user_id", "user_id"),
        Index("ix_contacts_contact_user_id", "contact_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(
        back_populates="contacts",
        foreign_keys=[user_id],
    )
    contact_user: Mapped[User] = relationship(
        back_populates="contacted_by",
        foreign_keys=[contact_user_id],
    )


class Conversation(Base):
    """A direct (1:1) or group conversation. One table covers both types.

    SQLite cannot uniquely constrain a pair of rows in conversation_members
    only when type='direct'. A nullable unique direct_pair_key is the MVP
    equivalent: canonical 'min_user_id:max_user_id' for direct chats, NULL
    for groups (SQLite unique indexes allow many NULLs).
    """

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("type IN ('direct', 'group')", name="ck_conversations_type"),
        CheckConstraint(
            "(type = 'direct' AND direct_pair_key IS NOT NULL) OR "
            "(type = 'group' AND direct_pair_key IS NULL)",
            name="ck_conversations_direct_pair_key",
        ),
        Index("ix_conversations_type", "type"),
        Index("ix_conversations_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    # Unique for direct chats only; NULL on groups so they are unconstrained.
    direct_pair_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    creator: Mapped[User | None] = relationship(
        back_populates="created_conversations",
    )
    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def make_direct_pair_key(user_id_a: int, user_id_b: int) -> str:
        """Return a canonical pair key so A-B and B-A map to the same direct chat."""
        low, high = sorted((user_id_a, user_id_b))
        return f"{low}:{high}"


class ConversationMember(Base):
    """Membership of a user in a conversation, including group role."""

    __tablename__ = "conversation_members"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_members_conversation_user",
        ),
        CheckConstraint(
            "role IN ('admin', 'member')",
            name="ck_conversation_members_role",
        ),
        Index("ix_conversation_members_conversation_id", "conversation_id"),
        Index("ix_conversation_members_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", server_default="member"
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime)

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Message(Base):
    """A persisted message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_sender_id", "sender_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship(back_populates="sent_messages")
    receipts: Mapped[list["MessageReceipt"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class MessageReceipt(Base):
    """Per-recipient delivery/read state for a message (required for groups)."""

    __tablename__ = "message_receipts"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            name="uq_message_receipts_message_user",
        ),
        CheckConstraint(
            "status IN ('sent', 'delivered', 'read')",
            name="ck_message_receipts_status",
        ),
        Index("ix_message_receipts_message_id", "message_id"),
        Index("ix_message_receipts_user_id", "user_id"),
        Index("ix_message_receipts_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sent", server_default="sent"
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)

    message: Mapped[Message] = relationship(back_populates="receipts")
    user: Mapped[User] = relationship(back_populates="message_receipts")


class AuthSession(Base):
    """Database-backed browser session created after mocked OTP auth."""

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="auth_sessions")
