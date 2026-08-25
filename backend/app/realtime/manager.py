"""Best-effort, group-scoped WebSocket event delivery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(frozen=True)
class GroupConnection:
    user_id: int
    websocket: WebSocket


class ConnectionManager:
    """Track authenticated group connections and safely broadcast to each group."""

    def __init__(self) -> None:
        self._connections: dict[int, list[GroupConnection]] = {}
        self._event_loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, group_id: int, user_id: int, websocket: WebSocket) -> None:
        """Accept and register a connection that has already passed authorization."""
        await websocket.accept()
        self._event_loop = asyncio.get_running_loop()
        self._connections.setdefault(group_id, []).append(
            GroupConnection(user_id=user_id, websocket=websocket)
        )

    async def disconnect(self, group_id: int, websocket: WebSocket) -> None:
        """Remove one connection without affecting other users or groups."""
        connections = self._connections.get(group_id, [])
        remaining = [
            connection
            for connection in connections
            if connection.websocket is not websocket
        ]
        if remaining:
            self._connections[group_id] = remaining
        else:
            self._connections.pop(group_id, None)

    async def broadcast(
        self,
        group_id: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an envelope only to active connections for ``group_id``."""
        envelope = {"type": event_type, "group_id": group_id, "payload": payload}
        for connection in list(self._connections.get(group_id, [])):
            try:
                await connection.websocket.send_json(envelope)
            except Exception:
                # A failed socket must never affect the successful REST mutation.
                await self.disconnect(group_id, connection.websocket)

    def broadcast_from_sync(
        self,
        group_id: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Schedule delivery from synchronous service code without blocking it."""
        event_loop = self._event_loop
        if event_loop is None or event_loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.broadcast(group_id, event_type, payload), event_loop
            )
        except RuntimeError:
            return
        future.add_done_callback(_consume_delivery_result)

    def remove_user_from_group(self, group_id: int, user_id: int) -> None:
        """Stop delivering group events to a user who was just removed."""
        connections = self._connections.get(group_id, [])
        removed = [connection for connection in connections if connection.user_id == user_id]
        remaining = [connection for connection in connections if connection.user_id != user_id]
        if remaining:
            self._connections[group_id] = remaining
        else:
            self._connections.pop(group_id, None)

        event_loop = self._event_loop
        if removed and event_loop is not None and not event_loop.is_closed():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    _close_connections(removed), event_loop
                )
            except RuntimeError:
                return
            future.add_done_callback(_consume_delivery_result)

    def connection_count(self, group_id: int) -> int:
        """Expose connection state for diagnostics and infrastructure tests."""
        return len(self._connections.get(group_id, []))


async def _close_connections(connections: list[GroupConnection]) -> None:
    for connection in connections:
        try:
            await connection.websocket.close(code=1008)
        except Exception:
            pass


def _consume_delivery_result(future: object) -> None:
    try:
        future.result()  # type: ignore[attr-defined]
    except Exception:
        pass


connection_manager = ConnectionManager()
