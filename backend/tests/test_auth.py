"""Authentication tests for mocked OTP onboarding (unittest, no extra deps)."""

from __future__ import annotations

import unittest
import uuid
from http.cookies import SimpleCookie

from fastapi import HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy import inspect

from app.auth.dependencies import get_current_user
from app.auth.router import login, logout, me, register
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.service import FIXED_OTP
from app.database import SessionLocal, engine, init_db
from app.main import app
from app.models import AuthSession, User


def _token_from_response(response: Response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers.get("set-cookie", ""))
    morsel = cookie.get("session_token")
    if morsel is None:
        raise AssertionError(f"missing session cookie: {response.headers}")
    return morsel.value


class AuthOnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_db()

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid.uuid4().hex[:10]
        self.created_user_ids: list[int] = []

    def tearDown(self) -> None:
        for user_id in self.created_user_ids:
            user = self.db.get(User, user_id)
            if user is not None:
                self.db.delete(user)
        self.db.commit()
        self.db.close()

    def _register(self, **overrides):
        payload = RegisterRequest(
            username=overrides.get("username", f"user_{self.suffix}"),
            phone=overrides.get("phone", f"+1555{self.suffix[:7]}"),
            display_name=overrides.get("display_name", "Test User"),
            avatar_url=overrides.get("avatar_url", "https://example.com/a.png"),
            otp=overrides.get("otp", FIXED_OTP),
        )
        response = Response()
        user = register(payload, response, self.db)
        self.created_user_ids.append(user.id)
        return user, response

    def test_openapi_includes_auth_routes(self) -> None:
        paths = app.openapi()["paths"]
        for path in ("/auth/register", "/auth/login", "/auth/me", "/auth/logout"):
            self.assertIn(path, paths)

    def test_existing_tables_and_auth_sessions(self) -> None:
        tables = set(inspect(engine).get_table_names())
        self.assertTrue(
            {
                "users",
                "contacts",
                "conversations",
                "conversation_members",
                "messages",
                "message_receipts",
                "auth_sessions",
            }.issubset(tables)
        )

    def test_register_success_sets_httponly_cookie(self) -> None:
        user, response = self._register()
        self.assertEqual(user.display_name, "Test User")
        header = response.headers.get("set-cookie", "").lower()
        self.assertIn("httponly", header)
        self.assertTrue(_token_from_response(response))
        session = self.db.query(AuthSession).filter_by(user_id=user.id).one()
        self.assertEqual(session.session_token, _token_from_response(response))

    def test_register_invalid_otp(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            self._register(otp="000000")
        self.assertEqual(caught.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_requires_username_or_phone(self) -> None:
        with self.assertRaises(ValidationError):
            RegisterRequest(display_name="Nobody", otp=FIXED_OTP)

    def test_duplicate_username(self) -> None:
        self._register()
        with self.assertRaises(HTTPException) as caught:
            self._register(phone=f"+1666{self.suffix[:7]}")
        self.assertEqual(caught.exception.status_code, status.HTTP_409_CONFLICT)

    def test_duplicate_phone(self) -> None:
        first, _ = self._register()
        with self.assertRaises(HTTPException) as caught:
            register(
                RegisterRequest(
                    username=f"other_{self.suffix}",
                    phone=first.phone,
                    display_name="Other",
                    otp=FIXED_OTP,
                ),
                Response(),
                self.db,
            )
        self.assertEqual(caught.exception.status_code, status.HTTP_409_CONFLICT)

    def test_invalid_avatar_url(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            self._register(avatar_url="javascript:alert(1)")
        self.assertEqual(caught.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_me(self) -> None:
        created, _ = self._register()
        login_response = Response()
        logged_in = login(
            LoginRequest(username=created.username, otp=FIXED_OTP),
            login_response,
            self.db,
        )
        self.assertEqual(logged_in.id, created.id)
        token = _token_from_response(login_response)
        current = get_current_user(db=self.db, session_token=token)
        self.assertEqual(current.id, created.id)
        self.assertEqual(me(current).id, created.id)

    def test_logout_then_me_fails(self) -> None:
        _, register_response = self._register()
        token = _token_from_response(register_response)
        logout_response = Response()
        result = logout(logout_response, self.db, token)
        self.assertEqual(result.message, "Logged out")
        with self.assertRaises(HTTPException) as caught:
            get_current_user(db=self.db, session_token=token)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_session(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            logout(Response(), self.db, None)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_without_session(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            get_current_user(db=self.db, session_token=None)
        self.assertEqual(caught.exception.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()
