"""Group member list / add / remove tests."""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException, Response, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP, SESSION_COOKIE_NAME
from app.conversations import service as conversations_service
from app.database import SessionLocal, init_db
from app.main import app
from app.messages import receipts as receipts_service
from app.messages import service as messages_service
from app.models import Conversation, ConversationMember, Message, User
from app.websocket.manager import manager


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


def _token(response: Response) -> str:
    header = response.headers.get("set-cookie", "")
    for part in header.split(";"):
        if part.strip().startswith(f"{SESSION_COOKIE_NAME}="):
            return part.split("=", 1)[1].strip()
    raise AssertionError(header)


class GroupMemberManagementTests(unittest.TestCase):
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
        self.db.expire_all()
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

    def _group(self, admin: User, *members: User) -> Conversation:
        group = conversations_service.create_group_conversation(
            self.db,
            admin,
            f"Team {self.suffix}",
            [user.id for user in members],
        )
        self.conversation_ids.append(group.id)
        return group

    def _direct(self, left: User, right: User) -> Conversation:
        conversation, _ = conversations_service.create_direct_conversation(
            self.db, left, right.id
        )
        self.conversation_ids.append(conversation.id)
        return conversation

    def _promote(self, conversation_id: int, user_id: int) -> None:
        member = self.db.query(ConversationMember).filter_by(
            conversation_id=conversation_id, user_id=user_id
        ).one()
        member.role = "admin"
        self.db.commit()

    def test_member_can_view_group_members(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        group = self._group(alice, bob)
        response = self.client.get(
            f"/conversations/{group.id}/members",
            headers=_cookie(bob_token),
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual({row["user_id"] for row in rows}, {alice.id, bob.id})
        alice_row = next(row for row in rows if row["user_id"] == alice.id)
        self.assertEqual(alice_row["role"], "admin")
        self.assertEqual(alice_row["display_name"], "Alice User")
        self.assertEqual(alice_row["username"], alice.username)
        self.assertEqual(alice_row["avatar_url"], "https://example.com/a.png")
        self.assertIn("joined_at", alice_row)
        self.assertIn("is_online", alice_row)
        self.assertIn("last_seen", alice_row)
        bob_row = next(row for row in rows if row["user_id"] == bob.id)
        self.assertEqual(bob_row["role"], "member")

    def test_non_member_and_unauthenticated_cannot_view_members(self) -> None:
        alice, _ = self._register("alice")
        bob, _ = self._register("bob")
        carol, carol_token = self._register("carol")
        group = self._group(alice, bob)
        forbidden = self.client.get(
            f"/conversations/{group.id}/members",
            headers=_cookie(carol_token),
        )
        self.assertEqual(forbidden.status_code, 403)
        unauth = self.client.get(f"/conversations/{group.id}/members")
        self.assertEqual(unauth.status_code, 401)

    def test_direct_and_missing_conversation_rejected(self) -> None:
        alice, token = self._register("alice")
        bob, _ = self._register("bob")
        direct = self._direct(alice, bob)
        direct_response = self.client.get(
            f"/conversations/{direct.id}/members",
            headers=_cookie(token),
        )
        self.assertEqual(direct_response.status_code, 400)
        missing = self.client.get(
            "/conversations/99999999/members",
            headers=_cookie(token),
        )
        self.assertEqual(missing.status_code, 404)

    def test_admin_can_add_member_and_duplicate_is_rejected(self) -> None:
        alice, alice_token = self._register("alice")
        bob, _ = self._register("bob")
        carol, _ = self._register("carol")
        group = self._group(alice, bob)
        added = self.client.post(
            f"/conversations/{group.id}/members",
            headers=_cookie(alice_token),
            json={"user_id": carol.id},
        )
        self.assertEqual(added.status_code, 201)
        body = added.json()
        self.assertEqual(body["user_id"], carol.id)
        self.assertEqual(body["role"], "member")
        listed = self.client.get(
            f"/conversations/{group.id}/members",
            headers=_cookie(alice_token),
        ).json()
        self.assertEqual({row["user_id"] for row in listed}, {alice.id, bob.id, carol.id})
        duplicate = self.client.post(
            f"/conversations/{group.id}/members",
            headers=_cookie(alice_token),
            json={"user_id": carol.id},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_add_member_authorization_and_validation(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, _ = self._register("carol")
        group = self._group(alice, bob)
        direct = self._direct(alice, bob)
        member_add = self.client.post(
            f"/conversations/{group.id}/members",
            headers=_cookie(bob_token),
            json={"user_id": carol.id},
        )
        self.assertEqual(member_add.status_code, 403)
        missing_user = self.client.post(
            f"/conversations/{group.id}/members",
            headers=_cookie(alice_token),
            json={"user_id": 99999999},
        )
        self.assertEqual(missing_user.status_code, 404)
        unauth = self.client.post(
            f"/conversations/{group.id}/members",
            json={"user_id": carol.id},
        )
        self.assertEqual(unauth.status_code, 401)
        on_direct = self.client.post(
            f"/conversations/{direct.id}/members",
            headers=_cookie(alice_token),
            json={"user_id": carol.id},
        )
        self.assertEqual(on_direct.status_code, 400)

    def test_admin_can_remove_member_and_history_remains(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, _ = self._register("carol")
        group = self._group(alice, bob, carol)
        message = messages_service.send_message(self.db, alice, group.id, "Keep me")
        message_id = message.id
        removed = self.client.delete(
            f"/conversations/{group.id}/members/{bob.id}",
            headers=_cookie(alice_token),
        )
        self.assertEqual(removed.status_code, 204)
        listed = self.client.get(
            f"/conversations/{group.id}/members",
            headers=_cookie(alice_token),
        ).json()
        self.assertEqual({row["user_id"] for row in listed}, {alice.id, carol.id})
        self.db.expire_all()
        stored = self.db.get(Message, message_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.content, "Keep me")
        group_row = self.db.get(Conversation, group.id)
        self.assertIsNotNone(group_row)
        remaining = {
            row.user_id
            for row in self.db.query(ConversationMember).filter_by(
                conversation_id=group.id
            )
        }
        self.assertEqual(remaining, {alice.id, carol.id})
        forbidden_view = self.client.get(
            f"/conversations/{group.id}/members",
            headers=_cookie(bob_token),
        )
        self.assertEqual(forbidden_view.status_code, 403)

    def test_remove_authorization_and_validation(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        carol, _ = self._register("carol")
        group = self._group(alice, bob, carol)
        direct = self._direct(alice, bob)
        member_remove = self.client.delete(
            f"/conversations/{group.id}/members/{carol.id}",
            headers=_cookie(bob_token),
        )
        self.assertEqual(member_remove.status_code, 403)
        missing = self.client.delete(
            f"/conversations/{group.id}/members/99999999",
            headers=_cookie(alice_token),
        )
        self.assertEqual(missing.status_code, 404)
        unauth = self.client.delete(f"/conversations/{group.id}/members/{bob.id}")
        self.assertEqual(unauth.status_code, 401)
        on_direct = self.client.delete(
            f"/conversations/{direct.id}/members/{bob.id}",
            headers=_cookie(alice_token),
        )
        self.assertEqual(on_direct.status_code, 400)

    def test_last_admin_cannot_be_removed_or_leave(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        group = self._group(alice, bob)
        self_leave = self.client.delete(
            f"/conversations/{group.id}/members/{alice.id}",
            headers=_cookie(alice_token),
        )
        self.assertEqual(self_leave.status_code, 400)
        self.assertIn("last group admin", self_leave.json()["detail"])
        listed = conversations_service.list_group_members(self.db, alice, group.id)
        self.assertEqual({row.user_id for row in listed}, {alice.id, bob.id})
        member_leave = self.client.delete(
            f"/conversations/{group.id}/members/{bob.id}",
            headers=_cookie(bob_token),
        )
        self.assertEqual(member_leave.status_code, 204)
        self.db.expire_all()
        remaining = conversations_service.list_group_members(self.db, alice, group.id)
        self.assertEqual({row.user_id for row in remaining}, {alice.id})
        self.assertEqual(remaining[0].role, "admin")

    def test_admin_can_remove_another_admin_when_one_remains(self) -> None:
        alice, alice_token = self._register("alice")
        bob, _ = self._register("bob")
        group = self._group(alice, bob)
        self._promote(group.id, bob.id)
        removed = self.client.delete(
            f"/conversations/{group.id}/members/{bob.id}",
            headers=_cookie(alice_token),
        )
        self.assertEqual(removed.status_code, 204)
        self.db.expire_all()
        remaining = conversations_service.list_group_members(self.db, alice, group.id)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].user_id, alice.id)
        self.assertEqual(remaining[0].role, "admin")

    def test_removed_member_loses_websocket_and_message_access(self) -> None:
        alice, alice_token = self._register("alice")
        bob, bob_token = self._register("bob")
        group = self._group(alice, bob)
        group_id = group.id
        bob_id = bob.id
        message = messages_service.send_message(self.db, alice, group_id, "Before")
        message_id = message.id
        self.db.commit()
        removed = self.client.delete(
            f"/conversations/{group_id}/members/{bob_id}",
            headers=_cookie(alice_token),
        )
        self.assertEqual(removed.status_code, 204)
        with self.assertRaises(WebSocketDisconnect) as caught:
            with self.client.websocket_connect(
                f"/ws/conversations/{group_id}",
                headers=_cookie(bob_token),
            ):
                pass
        self.assertEqual(caught.exception.code, 4403)
        self.db.expire_all()
        bob = self.db.get(User, bob_id)
        with self.assertRaises(HTTPException) as send_err:
            messages_service.send_message(self.db, bob, group_id, "Nope")
        self.assertEqual(send_err.exception.status_code, status.HTTP_403_FORBIDDEN)
        with self.assertRaises(HTTPException) as read_err:
            receipts_service.mark_message_read(self.db, bob, message_id, group_id)
        self.assertEqual(read_err.exception.status_code, status.HTTP_403_FORBIDDEN)
        with self.assertRaises(HTTPException) as delivered_err:
            receipts_service.mark_message_delivered(
                self.db, bob, message_id, group_id
            )
        self.assertEqual(
            delivered_err.exception.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_openapi_includes_member_routes(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/conversations/{conversation_id}/members", paths)
        self.assertIn("get", paths["/conversations/{conversation_id}/members"])
        self.assertIn("post", paths["/conversations/{conversation_id}/members"])
        self.assertIn(
            "/conversations/{conversation_id}/members/{user_id}", paths
        )
