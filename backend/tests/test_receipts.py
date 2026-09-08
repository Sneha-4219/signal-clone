"""Delivery and read receipt transition tests."""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException, Response, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth.dependencies import get_current_user
from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP, SESSION_COOKIE_NAME
from app.conversations import service as conversations_service
from app.database import SessionLocal, init_db
from app.main import app
from app.messages import receipts as receipts_service
from app.messages import service as messages_service
from app.models import Conversation, MessageReceipt, User
from app.websocket.manager import manager
from tests.ws_helpers import receive_of_type


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


def _token(response: Response) -> str:
    header = response.headers.get("set-cookie", "")
    for part in header.split(";"):
        if part.strip().startswith(f"{SESSION_COOKIE_NAME}="):
            return part.split("=", 1)[1].strip()
    raise AssertionError(header)


class ReceiptTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        manager.clear()
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user_ids: list[int] = []
        self.conversation_ids: list[int] = []
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        manager.clear()
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

    def _register(self, label: str) -> tuple[User, str]:
        response = Response()
        user = register(
            RegisterRequest(
                username=f"{label}_{self.suffix}",
                phone=f"+1555{self.suffix[:6]}{label[:1]}",
                display_name=f"{label.title()} User",
                avatar_url="https://example.com/a.png",
                otp=FIXED_OTP,
            ),
            response,
            self.db,
        )
        self.user_ids.append(user.id)
        return user, _token(response)

    def _direct(self, left: User, right: User) -> Conversation:
        conversation, _ = conversations_service.create_direct_conversation(
            self.db, left, right.id
        )
        self.conversation_ids.append(conversation.id)
        return conversation

    def _receipt(self, message_id: int, user_id: int) -> MessageReceipt:
        self.db.expire_all()
        row = self.db.query(MessageReceipt).filter_by(
            message_id=message_id, user_id=user_id
        ).one()
        return row

    def test_sent_to_delivered_to_read(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        receipt = self._receipt(message.id, bob.id)
        self.assertEqual(receipt.status, "sent")
        self.assertIsNone(receipt.delivered_at)

        delivered, changed = receipts_service.mark_message_delivered(
            self.db, bob, message.id, conversation.id
        )
        self.assertTrue(changed)
        self.assertEqual(delivered.status, "delivered")
        self.assertIsNotNone(delivered.delivered_at)
        self.assertIsNone(delivered.read_at)

        read, changed = receipts_service.mark_message_read(
            self.db, bob, message.id, conversation.id
        )
        self.assertTrue(changed)
        self.assertEqual(read.status, "read")
        self.assertIsNotNone(read.read_at)
        self.assertIsNotNone(read.delivered_at)
        self.assertLessEqual(read.delivered_at, read.read_at)

    def test_sent_to_read_sets_delivered_at(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        read, _ = receipts_service.mark_message_read(
            self.db, bob, message.id, conversation.id
        )
        self.assertEqual(read.status, "read")
        self.assertIsNotNone(read.delivered_at)
        self.assertIsNotNone(read.read_at)

    def test_cannot_move_backward(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        receipts_service.mark_message_read(self.db, bob, message.id, conversation.id)
        delivered, changed = receipts_service.mark_message_delivered(
            self.db, bob, message.id, conversation.id
        )
        self.assertFalse(changed)
        self.assertEqual(delivered.status, "read")

    def test_sender_cannot_mark_recipient_receipt(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        with self.assertRaises(HTTPException) as caught:
            receipts_service.mark_message_read(
                self.db, alice, message.id, conversation.id
            )
        self.assertEqual(caught.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_update_receipts(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        carol = self._register("carol")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        with self.assertRaises(HTTPException) as caught:
            receipts_service.mark_message_delivered(
                self.db, carol, message.id, conversation.id
            )
        self.assertEqual(caught.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_update_receipts(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            get_current_user(db=self.db, session_token=None)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        response = self.client.post(
            f"/conversations/{conversation.id}/messages/{message.id}/read"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_message_and_receipt(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        carol = self._register("carol")[0]
        conversation = self._direct(alice, bob)
        group = conversations_service.create_group_conversation(
            self.db, alice, f"Other {self.suffix}", [bob.id, carol.id]
        )
        self.conversation_ids.append(group.id)
        with self.assertRaises(HTTPException) as missing_message:
            receipts_service.mark_message_read(self.db, bob, 999999, conversation.id)
        self.assertEqual(missing_message.exception.status_code, status.HTTP_404_NOT_FOUND)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        with self.assertRaises(HTTPException) as wrong_conversation:
            receipts_service.mark_message_read(self.db, bob, message.id, group.id)
        self.assertEqual(
            wrong_conversation.exception.status_code, status.HTTP_404_NOT_FOUND
        )

    def test_repeated_events_are_idempotent(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        conversation = self._direct(alice, bob)
        message = messages_service.send_message(self.db, alice, conversation.id, "Hi")
        first, _ = receipts_service.mark_message_delivered(
            self.db, bob, message.id, conversation.id
        )
        second, changed = receipts_service.mark_message_delivered(
            self.db, bob, message.id, conversation.id
        )
        self.assertFalse(changed)
        self.assertEqual(first.delivered_at, second.delivered_at)
        read1, _ = receipts_service.mark_message_read(
            self.db, bob, message.id, conversation.id
        )
        read2, changed = receipts_service.mark_message_read(
            self.db, bob, message.id, conversation.id
        )
        self.assertFalse(changed)
        self.assertEqual(read1.read_at, read2.read_at)
        self.assertEqual(
            self.db.query(MessageReceipt).filter_by(message_id=message.id).count(), 1
        )

    def test_offline_recipient_stays_sent(self) -> None:
        alice, alice_token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        bob_id = bob.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(alice_token),
        ) as alice_ws:
            alice_ws.send_json({"type": "message", "content": "Offline bob"})
            event = receive_of_type(alice_ws, "message")
        self.db = SessionLocal()
        receipt = self._receipt(event["message"]["id"], bob_id)
        self.assertEqual(receipt.status, "sent")
        self.assertIsNone(receipt.delivered_at)

    def test_delivery_and_read_are_broadcast(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        bob_id = bob.id
        self.db.commit()
        self.db.close()
        with TestClient(app) as client:
            with client.websocket_connect(
                f"/ws/conversations/{conversation_id}",
                headers=_cookie(alice_token),
            ) as alice_ws:
                alice_ws.send_json({"type": "message", "content": "Live"})
                message_event = receive_of_type(alice_ws, "message")
                self.assertEqual(message_event["type"], "message")
                message_id = message_event["message"]["id"]
                with client.websocket_connect(
                    f"/ws/conversations/{conversation_id}",
                    headers=_cookie(bob_token),
                ) as bob_ws:
                    delivered_alice = receive_of_type(alice_ws, "receipt")
                    delivered_bob = receive_of_type(bob_ws, "receipt")
                    self.assertEqual(delivered_alice["type"], "receipt")
                    self.assertEqual(delivered_alice["status"], "delivered")
                    self.assertEqual(delivered_alice["user_id"], bob_id)
                    self.assertEqual(delivered_bob["status"], "delivered")
                    bob_ws.send_json({"type": "read", "message_id": message_id})
                    read_alice = receive_of_type(alice_ws, "receipt")
                    read_bob = receive_of_type(bob_ws, "receipt")
        self.assertEqual(read_alice["type"], "receipt")
        self.assertEqual(read_alice["status"], "read")
        self.assertEqual(read_bob["status"], "read")
        self.assertEqual(read_alice["user_id"], bob_id)
        self.db = SessionLocal()

    def test_group_receipts_are_independent(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        carol = self._register("carol")[0]
        group = conversations_service.create_group_conversation(
            self.db, alice, f"Receipts {self.suffix}", [bob.id, carol.id]
        )
        self.conversation_ids.append(group.id)
        message = messages_service.send_message(self.db, alice, group.id, "Team")
        receipts_service.mark_message_delivered(
            self.db, bob, message.id, group.id
        )
        receipts_service.mark_message_read(self.db, bob, message.id, group.id)
        bob_row = self._receipt(message.id, bob.id)
        carol_row = self._receipt(message.id, carol.id)
        self.assertEqual(bob_row.status, "read")
        self.assertEqual(carol_row.status, "sent")
        self.assertIsNone(carol_row.delivered_at)

    def test_one_recipient_cannot_modify_another(self) -> None:
        alice = self._register("alice")[0]
        bob = self._register("bob")[0]
        carol = self._register("carol")[0]
        group = conversations_service.create_group_conversation(
            self.db, alice, f"Own {self.suffix}", [bob.id, carol.id]
        )
        self.conversation_ids.append(group.id)
        message = messages_service.send_message(self.db, alice, group.id, "Hello")
        receipts_service.mark_message_read(self.db, bob, message.id, group.id)
        self.assertEqual(self._receipt(message.id, carol.id).status, "sent")
        self.assertEqual(self._receipt(message.id, bob.id).user_id, bob.id)

    def test_unauthenticated_cannot_send_read_on_websocket(self) -> None:
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f"/ws/conversations/{conversation.id}"):
                pass
