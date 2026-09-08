"""Online / last-seen presence WebSocket tests."""

from __future__ import annotations

import unittest
import uuid

from fastapi import Response
from fastapi.testclient import TestClient

from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP, SESSION_COOKIE_NAME
from app.conversations import service as conversations_service
from app.database import SessionLocal, init_db
from app.main import app
from app.models import Conversation, User
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


def _presence_for(websocket, user_id: int, *, limit: int = 20) -> dict:
    for _ in range(limit):
        event = receive_of_type(websocket, "presence")
        if event.get("user_id") == user_id:
            return event
    raise AssertionError(f"did not receive presence for {user_id}")


class PresenceTests(unittest.TestCase):
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

    def test_connect_marks_online_and_broadcasts(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        bob_id = bob.id
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(alice_token),
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(bob_token),
        ):
            event = receive_of_type(alice_ws, "presence")
            self.assertEqual(event["user_id"], bob_id)
            self.assertTrue(event["is_online"])
            probe = SessionLocal()
            self.assertTrue(probe.get(User, bob_id).is_online)
            probe.close()
        self.db = SessionLocal()
        alice = self.db.get(User, self.user_ids[0])
        bob = self.db.get(User, bob_id)
        self.assertFalse(alice.is_online)
        self.assertFalse(bob.is_online)
        self.assertIsNotNone(alice.last_seen)
        self.assertIsNotNone(bob.last_seen)

    def test_multiple_tabs_stay_online_until_final_disconnect(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        alice_id = alice.id
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(bob_token),
        ) as bob_ws:
            with self.client.websocket_connect(
                f"/ws/conversations/{conversation_id}",
                headers=_cookie(alice_token),
            ):
                receive_of_type(bob_ws, "presence")
                with self.client.websocket_connect(
                    f"/ws/conversations/{conversation_id}",
                    headers=_cookie(alice_token),
                ):
                    self.assertEqual(manager.user_connection_count(alice_id), 2)
                    probe = SessionLocal()
                    self.assertTrue(probe.get(User, alice_id).is_online)
                    probe.close()
                self.assertEqual(manager.user_connection_count(alice_id), 1)
                probe = SessionLocal()
                self.assertTrue(probe.get(User, alice_id).is_online)
                probe.close()
            offline = receive_of_type(bob_ws, "presence")
            self.assertEqual(offline["user_id"], alice_id)
            self.assertFalse(offline["is_online"])
            self.assertIsNotNone(offline["last_seen"])
        self.db = SessionLocal()
        alice = self.db.get(User, alice_id)
        self.assertFalse(alice.is_online)
        self.assertIsNotNone(alice.last_seen)
        previous_seen = alice.last_seen
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(alice_token),
        ):
            pass
        alice = self.db.get(User, alice_id)
        self.db.refresh(alice)
        self.assertFalse(alice.is_online)
        self.assertIsNotNone(alice.last_seen)
        self.assertGreaterEqual(alice.last_seen, previous_seen)

    def test_reconnect_marks_online_and_keeps_last_seen(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        alice_id = alice.id
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(alice_token),
        ):
            pass
        self.db = SessionLocal()
        alice = self.db.get(User, alice_id)
        self.assertFalse(alice.is_online)
        stored_seen = alice.last_seen
        self.assertIsNotNone(stored_seen)
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(bob_token),
        ) as bob_ws:
            with self.client.websocket_connect(
                f"/ws/conversations/{conversation_id}",
                headers=_cookie(alice_token),
            ):
                event = receive_of_type(bob_ws, "presence")
                self.assertEqual(event["user_id"], alice_id)
                self.assertTrue(event["is_online"])
                probe = SessionLocal()
                online = probe.get(User, alice_id)
                self.assertTrue(online.is_online)
                self.assertEqual(online.last_seen, stored_seen)
                probe.close()
        self.db = SessionLocal()
        alice = self.db.get(User, alice_id)
        self.assertIsNotNone(alice.last_seen)

    def test_unrelated_users_do_not_get_presence(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, carol_token = self._register("carol")
        ab = self._direct(alice, bob)
        ac = self._direct(alice, carol)
        ab_id, ac_id = ab.id, ac.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{ab_id}",
            headers=_cookie(alice_token),
        ), self.client.websocket_connect(
            f"/ws/conversations/{ab_id}",
            headers=_cookie(bob_token),
        ), self.client.websocket_connect(
            f"/ws/conversations/{ac_id}",
            headers=_cookie(carol_token),
        ) as carol_ws:
            carol_ws.send_json({"type": "message", "content": "ping"})
            event = receive_of_type(carol_ws, "message")
            self.assertEqual(event["type"], "message")
        self.db = SessionLocal()

    def test_group_presence_is_scoped(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, carol_token = self._register("carol")
        outsider, outsider_token = self._register("dave")
        alice_id = alice.id
        group = conversations_service.create_group_conversation(
            self.db, alice, f"Team {self.suffix}", [bob.id, carol.id]
        )
        other = self._direct(alice, outsider)
        group_id, other_id = group.id, other.id
        self.conversation_ids.append(group_id)
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(bob_token),
        ) as bob_ws, self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(carol_token),
        ) as carol_ws, self.client.websocket_connect(
            f"/ws/conversations/{other_id}",
            headers=_cookie(outsider_token),
        ) as outsider_ws, self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(alice_token),
        ):
            bob_event = _presence_for(bob_ws, alice_id)
            carol_event = _presence_for(carol_ws, alice_id)
            self.assertTrue(bob_event["is_online"])
            self.assertTrue(carol_event["is_online"])
            outsider_ws.send_json({"type": "message", "content": "ping"})
            outsider_event = receive_of_type(outsider_ws, "message")
            self.assertEqual(outsider_event["type"], "message")
        self.db = SessionLocal()
