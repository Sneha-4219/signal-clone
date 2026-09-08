"""Helpers for WebSocket tests that may also receive presence/typing events."""

from __future__ import annotations


def receive_of_type(websocket, expected: str, *, limit: int = 20) -> dict:
    """Skip ephemeral presence/typing events until the expected type arrives."""
    skipped = {"presence", "typing"}
    if expected != "receipt":
        skipped.add("receipt")
    for _ in range(limit):
        event = websocket.receive_json()
        if event.get("type") == expected:
            return event
        if event.get("type") in skipped:
            continue
        raise AssertionError(f"expected {expected}, got {event}")
    raise AssertionError(f"did not receive {expected}")
