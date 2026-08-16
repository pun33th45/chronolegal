"""Regression test for ConnectionManager's multi-connection tracking.

Before the fix, _connections was keyed str -> single WebSocket, so a
second connection for the same user_id silently overwrote the first, and
that first connection's disconnect() then popped the (still-open) second
connection out of the map entirely — leaving it registered nowhere, so
manager.send() would become a silent no-op for it.
"""

import pytest

from app.api.websocket import ConnectionManager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def accept(self) -> None:
        pass

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


@pytest.mark.asyncio
async def test_second_connection_survives_first_connections_disconnect():
    manager = ConnectionManager()
    ws_tab_1 = _FakeWebSocket()
    ws_tab_2 = _FakeWebSocket()

    await manager.connect("user-1", ws_tab_1)
    await manager.connect("user-1", ws_tab_2)

    # The first tab disconnects (e.g. closed) — this must not deregister
    # the second, still-open tab.
    manager.disconnect("user-1", ws_tab_1)

    await manager.send("user-1", {"type": "pong"})

    assert ws_tab_2.sent, "second connection should still receive messages"
    assert not ws_tab_1.sent


@pytest.mark.asyncio
async def test_disconnect_removes_only_the_specified_connection():
    manager = ConnectionManager()
    ws_a = _FakeWebSocket()
    ws_b = _FakeWebSocket()

    await manager.connect("user-1", ws_a)
    await manager.connect("user-1", ws_b)

    manager.disconnect("user-1", ws_a)

    assert ws_a not in manager._connections.get("user-1", set())
    assert ws_b in manager._connections.get("user-1", set())
