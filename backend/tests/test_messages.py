"""Messaging REST API tests (unittest, no extra deps)."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime

from fastapi import HTTPException, Response, status
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP
from app.conversations import service as conversations_service
from app.database import SessionLocal, init_db
from app.main import app
from app.messages import service as messages_service
from app.messages.schemas import MAX_MESSAGE_LENGTH, SendMessageRequest
from app.models import Conversation, Message, MessageReceipt, User


def _iter_api_routes():
    for route in app.routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from nested.routes
        else:
            yield route


def _route_calls_get_current_user(path_prefix: str) -> None:
    matched = False
    for route in _iter_api_routes():
        path = getattr(route, "path", "") or ""
        dependant = getattr(route, "dependant", None)
        if not path.startswith(path_prefix) or dependant is None:
            continue
        matched = True
        names = [dep.call.__name__ for dep in dependant.dependencies if getattr(dep, "call", None)]
        assert "get_current_user" in names, f"{path} missing get_current_user: {names}"
    assert matched, f"no routes for {path_prefix}"


class MessagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user_ids: list[int] = []
        self.conversation_ids: list[int] = []

    def tearDown(self) -> None:
        for conversation_id in self.conversation_ids:
            conversation = self.db.get(Conversation, conversation_id)
            if conversation is not None:
                self.db.delete(conversation)
        self.db.commit()
        for user_id in self.user_ids:
            user = self.db.get(User, user_id)
            if user is not None:
                self.db.delete(user)
        self.db.commit()
        self.db.close()

    def _register(self, label: str) -> User:
        user = register(
            RegisterRequest(
                username=f"{label}_{self.suffix}",
                phone=f"+1555{self.suffix[:6]}{label[:1]}",
                display_name=f"{label.title()} User",
                avatar_url="https://example.com/a.png",
                otp=FIXED_OTP,
            ),
            Response(),
            self.db,
        )
        self.user_ids.append(user.id)
        return user

    def _direct(self, alice: User, bob: User) -> Conversation:
        conversation, _ = conversations_service.create_direct_conversation(
            self.db, alice, bob.id
        )
        self.conversation_ids.append(conversation.id)
        return conversation

    def test_member_can_send_and_message_is_persisted(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(
            self.db, alice, conversation.id, "  Hello  "
        )
        self.assertEqual(message.sender_id, alice.id)
        self.assertEqual(message.content, "Hello")
        stored = self.db.get(Message, message.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.content, "Hello")
        self.assertEqual(stored.conversation_id, conversation.id)

    def test_blank_and_whitespace_and_length_rejected(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.assertRaises(ValidationError):
            SendMessageRequest(content="")
        with self.assertRaises(ValidationError):
            SendMessageRequest(content="   ")
        with self.assertRaises(ValidationError):
            SendMessageRequest(content="x" * (MAX_MESSAGE_LENGTH + 1))
        with self.assertRaises(HTTPException) as blank:
            messages_service.send_message(self.db, alice, conversation.id, "")
        self.assertEqual(blank.exception.status_code, status.HTTP_400_BAD_REQUEST)
        with self.assertRaises(HTTPException) as whitespace:
            messages_service.send_message(self.db, alice, conversation.id, " \n\t ")
        self.assertEqual(whitespace.exception.status_code, status.HTTP_400_BAD_REQUEST)
        with self.assertRaises(HTTPException) as too_long:
            messages_service.send_message(
                self.db, alice, conversation.id, "x" * (MAX_MESSAGE_LENGTH + 1)
            )
        self.assertEqual(too_long.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_conversation_updated_at_changes(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        conversation = self._direct(alice, bob)
        conversation.updated_at = datetime(2020, 1, 1)
        self.db.commit()
        message = messages_service.send_message(
            self.db, alice, conversation.id, "Ping"
        )
        self.db.refresh(conversation)
        self.assertEqual(conversation.updated_at, message.created_at)
        self.assertNotEqual(conversation.updated_at, datetime(2020, 1, 1))

    def test_direct_receipts_exclude_sender(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(
            self.db, alice, conversation.id, "Hi"
        )
        receipts = list(
            self.db.query(MessageReceipt).filter_by(message_id=message.id)
        )
        self.assertEqual({row.user_id for row in receipts}, {bob.id})
        self.assertTrue(all(row.status == "sent" for row in receipts))
        self.assertNotIn(alice.id, {row.user_id for row in receipts})

    def test_group_receipts_for_every_other_member(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        carol = self._register("carol")
        group = conversations_service.create_group_conversation(
            self.db, alice, "Team", [bob.id, carol.id]
        )
        self.conversation_ids.append(group.id)
        message = messages_service.send_message(
            self.db, alice, group.id, "Hello team"
        )
        receipts = list(
            self.db.query(MessageReceipt).filter_by(message_id=message.id)
        )
        self.assertEqual({row.user_id for row in receipts}, {bob.id, carol.id})
        self.assertTrue(all(row.status == "sent" for row in receipts))

    def test_history_oldest_to_newest_and_pagination(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        conversation = self._direct(alice, bob)
        messages_service.send_message(self.db, alice, conversation.id, "one")
        messages_service.send_message(self.db, bob, conversation.id, "two")
        messages_service.send_message(self.db, alice, conversation.id, "three")
        page, total = messages_service.list_messages(
            self.db, alice, conversation.id, limit=2, offset=0
        )
        self.assertEqual(total, 3)
        self.assertEqual([row.content for row in page], ["one", "two"])
        page2, _ = messages_service.list_messages(
            self.db, alice, conversation.id, limit=2, offset=2
        )
        self.assertEqual([row.content for row in page2], ["three"])
        all_rows, _ = messages_service.list_messages(
            self.db, bob, conversation.id, limit=50, offset=0
        )
        self.assertEqual([row.content for row in all_rows], ["one", "two", "three"])

    def test_unauthenticated_cannot_retrieve_messages(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            get_current_user(db=self.db, session_token=None)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        _route_calls_get_current_user("/conversations/{conversation_id}/messages")

    def test_non_member_cannot_read_or_send(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        carol = self._register("carol")
        conversation = self._direct(alice, bob)
        with self.assertRaises(HTTPException) as read:
            messages_service.list_messages(self.db, carol, conversation.id)
        self.assertEqual(read.exception.status_code, status.HTTP_403_FORBIDDEN)
        with self.assertRaises(HTTPException) as send:
            messages_service.send_message(self.db, carol, conversation.id, "Nope")
        self.assertEqual(send.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_conversation_id(self) -> None:
        alice = self._register("alice")
        with self.assertRaises(HTTPException) as caught:
            messages_service.send_message(self.db, alice, 99999999, "Hello")
        self.assertEqual(caught.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_openapi_includes_message_routes(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/conversations/{conversation_id}/messages", paths)
        methods = {method.upper() for method in paths["/conversations/{conversation_id}/messages"]}
        self.assertIn("GET", methods)
        self.assertIn("POST", methods)


if __name__ == "__main__":
    unittest.main()
