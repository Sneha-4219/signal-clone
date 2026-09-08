"""Deployment-aware settings with local-development defaults."""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def cors_origins() -> list[str]:
    origins = list(_LOCAL_FRONTEND_ORIGINS)
    extra = os.environ.get("FRONTEND_ORIGIN", "")
    for origin in extra.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)
    return origins


def cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes"}


def session_cookie_flags() -> dict[str, str | bool]:
    if cookie_secure():
        return {
            "httponly": True,
            "samesite": "none",
            "secure": True,
            "path": "/",
        }
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": False,
        "path": "/",
    }


def database_file() -> Path:
    override = os.environ.get("DATABASE_PATH", "").strip()
    if override:
        return Path(override)
    return BACKEND_DIR / "signal.db"
