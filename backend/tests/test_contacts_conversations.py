"""Contacts and conversations API tests (unittest, no extra deps)."""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException, Response, status
from pydantic import ValidationError

from app.auth.dependencies import get_current_user
from app.auth.router import register
from app.auth.schemas import RegisterRequest
from app.auth.service import FIXED_OTP
from app.contacts import service as contacts_service
from app.conversations import service as conversations_service
from app.conversations.schemas import GroupConversationRequest
from app.database import SessionLocal, init_db
from app.main import app
from app.models import Conversation, User


def _iter_api_routes():
    """Yield APIRoute objects, including those nested under FastAPI included routers."""
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


class ContactsConversationsTests(unittest.TestCase):
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

    def _register(self, label: str, display_name: str | None = None) -> User:
        payload = RegisterRequest(
            username=f"{label}_{self.suffix}",
            phone=f"+1555{self.suffix[:6]}{label[:1]}",
            display_name=display_name or f"{label.title()} User",
            avatar_url="https://example.com/a.png",
            otp=FIXED_OTP,
        )
        user = register(payload, Response(), self.db)
        self.user_ids.append(user.id)
        return user

    def _track(self, conversation: Conversation) -> Conversation:
        self.conversation_ids.append(conversation.id)
        return conversation

    def test_search_users_and_excludes_self(self) -> None:
        alice = self._register("alice", "Alice Search")
        bob = self._register("bob", "Bob Search")
        hits = contacts_service.search_users(self.db, alice, "search")
        ids = [user.id for user in hits]
        self.assertIn(bob.id, ids)
        self.assertNotIn(alice.id, ids)

    def test_add_list_and_remove_contact(self) -> None:
        alice = self._register("alice", "Alice")
        bob = self._register("bob", "Bob")
        contact = contacts_service.add_contact(self.db, alice, bob.id)
        self.assertEqual(contact.contact_user_id, bob.id)
        listed = contacts_service.list_contacts(self.db, alice)
        self.assertEqual([row.contact_user_id for row in listed], [bob.id])
        contacts_service.remove_contact(self.db, alice, bob.id)
        self.assertEqual(contacts_service.list_contacts(self.db, alice), [])

    def test_cannot_add_self_as_contact(self) -> None:
        alice = self._register("alice")
        with self.assertRaises(HTTPException) as caught:
            contacts_service.add_contact(self.db, alice, alice.id)
        self.assertEqual(caught.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_contact_rejected(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        contacts_service.add_contact(self.db, alice, bob.id)
        with self.assertRaises(HTTPException) as caught:
            contacts_service.add_contact(self.db, alice, bob.id)
        self.assertEqual(caught.exception.status_code, status.HTTP_409_CONFLICT)

    def test_create_direct_conversation_and_reuse_pair_key(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        first, created = conversations_service.create_direct_conversation(
            self.db, alice, bob.id
        )
        self._track(first)
        self.assertTrue(created)
        expected_key = Conversation.make_direct_pair_key(alice.id, bob.id)
        self.assertEqual(first.direct_pair_key, expected_key)
        self.assertEqual(
            Conversation.make_direct_pair_key(bob.id, alice.id), expected_key
        )
        second, created_again = conversations_service.create_direct_conversation(
            self.db, bob, alice.id
        )
        self.assertFalse(created_again)
        self.assertEqual(second.id, first.id)
        self.assertEqual(len(first.members), 2)
        self.assertIsNotNone(
            conversations_service.other_user(first, alice.id)
        )
        self.assertEqual(conversations_service.other_user(first, alice.id).id, bob.id)

    def test_unauthenticated_cannot_access_conversations(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            get_current_user(db=self.db, session_token=None)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        _route_calls_get_current_user("/conversations")
        _route_calls_get_current_user("/contacts")

    def test_only_members_can_access_conversation(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        carol = self._register("carol")
        conversation, _ = conversations_service.create_direct_conversation(
            self.db, alice, bob.id
        )
        self._track(conversation)
        loaded = conversations_service.get_conversation(self.db, alice, conversation.id)
        self.assertEqual(loaded.id, conversation.id)
        with self.assertRaises(HTTPException) as caught:
            conversations_service.get_conversation(self.db, carol, conversation.id)
        self.assertEqual(caught.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_group_admin_and_duplicate_member_ids(self) -> None:
        alice = self._register("alice")
        bob = self._register("bob")
        group = conversations_service.create_group_conversation(
            self.db,
            alice,
            "Project",
            [bob.id, bob.id, alice.id],
        )
        self._track(group)
        self.assertEqual(group.type, "group")
        self.assertIsNone(group.direct_pair_key)
        roles = {member.user_id: member.role for member in group.members}
        self.assertEqual(roles[alice.id], "admin")
        self.assertEqual(roles[bob.id], "member")
        self.assertEqual(len(group.members), 2)

    def test_invalid_group_member_ids_rejected(self) -> None:
        alice = self._register("alice")
        with self.assertRaises(HTTPException) as caught:
            conversations_service.create_group_conversation(
                self.db, alice, "Broken", [99999999]
            )
        self.assertEqual(caught.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_blank_group_name_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            GroupConversationRequest(name="   ", member_ids=[])

    def test_openapi_includes_new_routes(self) -> None:
        paths = app.openapi()["paths"]
        for path in (
            "/contacts/search",
            "/contacts",
            "/contacts/{user_id}",
            "/conversations",
            "/conversations/direct",
            "/conversations/group",
            "/conversations/{conversation_id}",
            "/conversations/{conversation_id}/members",
            "/conversations/{conversation_id}/members/{user_id}",
        ):
            self.assertIn(path, paths)


if __name__ == "__main__":
    unittest.main()
