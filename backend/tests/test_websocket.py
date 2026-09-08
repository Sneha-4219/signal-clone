"""WebSocket real-time messaging tests."""

from __future__ import annotations

import unittest
import uuid

from fastapi import Response
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP, SESSION_COOKIE_NAME
from app.conversations import service as conversations_service
from app.database import SessionLocal, init_db
from app.main import app
from app.messages.schemas import MAX_MESSAGE_LENGTH
from app.models import Conversation, Message, MessageReceipt, User
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


class WebSocketMessagingTests(unittest.TestCase):
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

    def test_authenticated_member_can_connect(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(token),
        ) as websocket:
            self.assertEqual(manager.count(conversation.id), 1)
            self.assertIn(alice.id, manager.user_ids(conversation.id))
        self.assertEqual(manager.count(conversation.id), 0)

    def test_unauthenticated_cannot_connect(self) -> None:
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client.websocket_connect(f"/ws/conversations/{conversation.id}"):
                pass
        self.assertEqual(caught.exception.code, 4401)

    def test_non_member_cannot_connect(self) -> None:
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        carol, carol_token = self._register("carol")
        conversation = self._direct(alice, bob)
        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client.websocket_connect(
                f"/ws/conversations/{conversation.id}",
                headers=_cookie(carol_token),
            ):
                pass
        self.assertEqual(caught.exception.code, 4403)

    def test_member_send_persists_and_broadcasts(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(alice_token),
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(bob_token),
        ) as bob_ws:
            alice_ws.send_json({"type": "message", "content": "Hello"})
            alice_event = receive_of_type(alice_ws, "message")
            bob_event = receive_of_type(bob_ws, "message")
        self.assertEqual(alice_event["type"], "message")
        self.assertEqual(bob_event["type"], "message")
        self.assertEqual(alice_event["message"]["content"], "Hello")
        self.assertEqual(alice_event["message"]["sender_id"], alice.id)
        self.assertEqual(alice_event["message"]["id"], bob_event["message"]["id"])
        self.db.expire_all()
        stored = self.db.get(Message, alice_event["message"]["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored.sender_id, alice.id)
        receipts = list(self.db.query(MessageReceipt).filter_by(message_id=stored.id))
        self.assertEqual({row.user_id for row in receipts}, {bob.id})
        self.assertTrue(all(row.status == "delivered" for row in receipts))

    def test_unrelated_conversation_does_not_receive(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, carol_token = self._register("carol")
        direct_ab = self._direct(alice, bob)
        direct_ac = self._direct(alice, carol)
        with self.client.websocket_connect(
            f"/ws/conversations/{direct_ab.id}",
            headers=_cookie(alice_token),
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{direct_ab.id}",
            headers=_cookie(bob_token),
        ) as bob_ws, self.client.websocket_connect(
            f"/ws/conversations/{direct_ac.id}",
            headers=_cookie(carol_token),
        ) as carol_ws:
            alice_ws.send_json({"type": "message", "content": "Only Bob"})
            receive_of_type(alice_ws, "message")
            receive_of_type(bob_ws, "message")
            carol_ws.send_json({"type": "message", "content": "Only Alice"})
            carol_event = receive_of_type(carol_ws, "message")
        self.assertEqual(carol_event["message"]["content"], "Only Alice")
        self.assertNotEqual(carol_event["message"]["content"], "Only Bob")

    def test_group_members_receive_group_messages(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, carol_token = self._register("carol")
        group = conversations_service.create_group_conversation(
            self.db, alice, f"WS {self.suffix}", [bob.id, carol.id]
        )
        self.conversation_ids.append(group.id)
        with self.client.websocket_connect(
            f"/ws/conversations/{group.id}",
            headers=_cookie(alice_token),
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{group.id}",
            headers=_cookie(bob_token),
        ) as bob_ws, self.client.websocket_connect(
            f"/ws/conversations/{group.id}",
            headers=_cookie(carol_token),
        ) as carol_ws:
            alice_ws.send_json({"type": "message", "content": "Team hello"})
            events = [
                receive_of_type(alice_ws, "message"),
                receive_of_type(bob_ws, "message"),
                receive_of_type(carol_ws, "message"),
            ]
        contents = {event["message"]["content"] for event in events}
        senders = {event["message"]["sender_id"] for event in events}
        self.assertEqual(contents, {"Team hello"})
        self.assertEqual(senders, {alice.id})

    def test_invalid_json_and_unsupported_type(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(token),
        ) as websocket:
            websocket.send_text("not-json")
            invalid = websocket.receive_json()
            websocket.send_json({"type": "reaction", "content": "x"})
            unsupported = websocket.receive_json()
        self.assertEqual(invalid["type"], "error")
        self.assertEqual(invalid["detail"], "Invalid JSON")
        self.assertEqual(unsupported["type"], "error")
        self.assertEqual(unsupported["detail"], "Unsupported event type")

    def test_blank_and_too_long_messages_rejected(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(token),
        ) as websocket:
            websocket.send_json({"type": "message", "content": "   "})
            blank = websocket.receive_json()
            websocket.send_json(
                {"type": "message", "content": "x" * (MAX_MESSAGE_LENGTH + 1)}
            )
            too_long = websocket.receive_json()
        self.assertEqual(blank["type"], "error")
        self.assertEqual(too_long["type"], "error")
        self.db.expire_all()
        count = self.db.query(Message).filter_by(conversation_id=conversation.id).count()
        self.assertEqual(count, 0)

    def test_multiple_tabs_and_disconnect_cleanup(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation.id}",
            headers=_cookie(token),
        ) as first:
            with self.client.websocket_connect(
                f"/ws/conversations/{conversation.id}",
                headers=_cookie(token),
            ) as second:
                self.assertEqual(manager.count(conversation.id), 2)
                first.send_json({"type": "message", "content": "From tab"})
                receive_of_type(first, "message")
                receive_of_type(second, "message")
            self.assertEqual(manager.count(conversation.id), 1)
        self.assertEqual(manager.count(conversation.id), 0)

    def test_websocket_route_is_registered(self) -> None:
        paths = [
            getattr(route, "path", "")
            or getattr(getattr(route, "original_router", None), "prefix", "")
            for route in app.routes
        ]
        nested = []
        for route in app.routes:
            router = getattr(route, "original_router", None)
            if router is None:
                continue
            nested.extend(getattr(item, "path", "") for item in router.routes)
        self.assertIn("/ws/conversations/{conversation_id}", nested + paths)
