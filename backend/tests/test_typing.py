"""Typing indicator WebSocket tests."""

from __future__ import annotations

import unittest
import uuid

from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from starlette.websockets import WebSocketDisconnect

from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP, SESSION_COOKIE_NAME
from app.conversations import service as conversations_service
from app.database import SessionLocal, engine, init_db
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


class TypingIndicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        manager.clear()
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.user_ids: list[int] = []
        self.conversation_ids: list[int] = []
        self._client_ctx = TestClient(app)
        self.client = self._client_ctx.__enter__()

    def tearDown(self) -> None:
        self._client_ctx.__exit__(None, None, None)
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

    def test_typing_true_and_false_reach_other_members_not_sender(self) -> None:
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
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(bob_token),
        ) as bob_ws:
            receive_of_type(alice_ws, "presence")
            alice_ws.send_json({"type": "typing", "is_typing": True})
            started = receive_of_type(bob_ws, "typing")
            self.assertEqual(started["user_id"], alice_id)
            self.assertTrue(started["is_typing"])
            alice_ws.send_json({"type": "typing", "is_typing": False})
            stopped = receive_of_type(bob_ws, "typing")
            self.assertFalse(stopped["is_typing"])
            alice_ws.send_json({"type": "message", "content": "still here"})
            receive_of_type(alice_ws, "message")
            receive_of_type(bob_ws, "message")
        self.db = SessionLocal()

    def test_unrelated_conversation_does_not_get_typing(self) -> None:
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
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{ab_id}",
            headers=_cookie(bob_token),
        ) as bob_ws:
            receive_of_type(alice_ws, "presence")
            alice_ws.send_json({"type": "typing", "is_typing": True})
            receive_of_type(bob_ws, "typing")
            alice_ws.send_json({"type": "typing", "is_typing": False})
            receive_of_type(bob_ws, "typing")
            alice_ws.send_json({"type": "message", "content": "done"})
            receive_of_type(alice_ws, "message")
            receive_of_type(bob_ws, "message")
        with self.client.websocket_connect(
            f"/ws/conversations/{ac_id}",
            headers=_cookie(carol_token),
        ) as carol_ws:
            carol_ws.send_json({"type": "message", "content": "unrelated"})
            carol_event = receive_of_type(carol_ws, "message")
            self.assertEqual(carol_event["type"], "message")
        self.db = SessionLocal()

    def test_group_typing_is_scoped(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, carol_token = self._register("carol")
        alice_id = alice.id
        group = conversations_service.create_group_conversation(
            self.db, alice, f"Type {self.suffix}", [bob.id, carol.id]
        )
        group_id = group.id
        self.conversation_ids.append(group_id)
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(alice_token),
        ) as alice_ws, self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(bob_token),
        ) as bob_ws, self.client.websocket_connect(
            f"/ws/conversations/{group_id}",
            headers=_cookie(carol_token),
        ) as carol_ws:
            alice_ws.send_json({"type": "typing", "is_typing": True})
            bob_event = receive_of_type(bob_ws, "typing")
            carol_event = receive_of_type(carol_ws, "typing")
            self.assertEqual(bob_event["user_id"], alice_id)
            self.assertEqual(carol_event["user_id"], alice_id)
            alice_ws.send_json({"type": "typing", "is_typing": False})
            receive_of_type(bob_ws, "typing")
            receive_of_type(carol_ws, "typing")
            alice_ws.send_json({"type": "message", "content": "done"})
            receive_of_type(alice_ws, "message")
            receive_of_type(bob_ws, "message")
            receive_of_type(carol_ws, "message")
        self.db = SessionLocal()

    def test_non_member_and_unauthenticated_cannot_type(self) -> None:
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        carol, carol_token = self._register("carol")
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(f"/ws/conversations/{conversation_id}"):
                pass
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(
                f"/ws/conversations/{conversation_id}",
                headers=_cookie(carol_token),
            ):
                pass

    def test_malformed_typing_is_safe(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(token),
        ) as websocket:
            websocket.send_json({"type": "typing"})
            missing = websocket.receive_json()
            websocket.send_json({"type": "typing", "is_typing": "yes"})
            invalid = websocket.receive_json()
        self.assertEqual(missing["type"], "error")
        self.assertEqual(invalid["type"], "error")
        self.db = SessionLocal()

    def test_typing_is_ephemeral_and_cleared_on_disconnect(self) -> None:
        alice, alice_token = self._register("alice")
        bob, _ = self._register("bob")
        alice_id = alice.id
        conversation = self._direct(alice, bob)
        conversation_id = conversation.id
        self.db.commit()
        self.db.close()
        with self.client.websocket_connect(
            f"/ws/conversations/{conversation_id}",
            headers=_cookie(alice_token),
        ) as alice_ws:
            alice_ws.send_json({"type": "typing", "is_typing": True})
            alice_ws.send_json({"type": "noop"})
            error = alice_ws.receive_json()
            self.assertEqual(error["type"], "error")
            self.assertTrue(manager.is_typing(conversation_id, alice_id))
            alice_ws.send_json({"type": "typing", "is_typing": False})
            alice_ws.send_json({"type": "noop"})
            alice_ws.receive_json()
            self.assertFalse(manager.is_typing(conversation_id, alice_id))
        self.assertFalse(manager.is_typing(conversation_id, alice_id))
        self.assertNotIn("typing", inspect(engine).get_table_names())
        self.db = SessionLocal()
