"""In-process WebSocket connection tracking for conversation rooms."""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    """Track multiple sockets per user per conversation. No external broker."""

    def __init__(self) -> None:
        self._rooms: dict[int, list[tuple[int, WebSocket]]] = {}
        self._typing: set[tuple[int, int]] = set()

    def connect(self, conversation_id: int, user_id: int, websocket: WebSocket) -> None:
        self._rooms.setdefault(conversation_id, []).append((user_id, websocket))

    def disconnect(self, websocket: WebSocket) -> None:
        empty: list[int] = []
        for conversation_id, connections in self._rooms.items():
            remaining = [
                (user_id, socket)
                for user_id, socket in connections
                if socket is not websocket
            ]
            if remaining:
                self._rooms[conversation_id] = remaining
            else:
                empty.append(conversation_id)
        for conversation_id in empty:
            del self._rooms[conversation_id]

    def clear(self) -> None:
        self._rooms.clear()
        self._typing.clear()

    def count(self, conversation_id: int | None = None) -> int:
        if conversation_id is None:
            return sum(len(items) for items in self._rooms.values())
        return len(self._rooms.get(conversation_id, []))

    def user_ids(self, conversation_id: int) -> set[int]:
        return {user_id for user_id, _ in self._rooms.get(conversation_id, [])}

    def pop_user_from_conversation(
        self, conversation_id: int, user_id: int
    ) -> list[WebSocket]:
        """Drop a user's sockets from one conversation room and return them."""
        connections = self._rooms.get(conversation_id, [])
        kept: list[tuple[int, WebSocket]] = []
        removed: list[WebSocket] = []
        for uid, socket in connections:
            if uid == user_id:
                removed.append(socket)
            else:
                kept.append((uid, socket))
        if kept:
            self._rooms[conversation_id] = kept
        elif conversation_id in self._rooms:
            del self._rooms[conversation_id]
        self.clear_typing(conversation_id, user_id)
        return removed

    def user_connection_count(self, user_id: int) -> int:
        return sum(
            1
            for connections in self._rooms.values()
            for uid, _socket in connections
            if uid == user_id
        )

    def conversation_ids_for_user(self, user_id: int) -> set[int]:
        return {
            conversation_id
            for conversation_id, connections in self._rooms.items()
            if any(uid == user_id for uid, _socket in connections)
        }

    def set_typing(self, conversation_id: int, user_id: int, is_typing: bool) -> None:
        key = (conversation_id, user_id)
        if is_typing:
            self._typing.add(key)
        else:
            self._typing.discard(key)

    def is_typing(self, conversation_id: int, user_id: int) -> bool:
        return (conversation_id, user_id) in self._typing

    def clear_typing(self, conversation_id: int, user_id: int) -> bool:
        key = (conversation_id, user_id)
        if key in self._typing:
            self._typing.discard(key)
            return True
        return False

    async def broadcast(self, conversation_id: int, payload: dict) -> None:
        for _user_id, socket in list(self._rooms.get(conversation_id, [])):
            try:
                await socket.send_json(payload)
            except Exception:
                self.disconnect(socket)

    async def broadcast_to_others(
        self, conversation_id: int, exclude_user_id: int, payload: dict
    ) -> None:
        for user_id, socket in list(self._rooms.get(conversation_id, [])):
            if user_id == exclude_user_id:
                continue
            try:
                await socket.send_json(payload)
            except Exception:
                pass


manager = ConnectionManager()
