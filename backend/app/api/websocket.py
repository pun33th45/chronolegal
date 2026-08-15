"""
WebSocket endpoint for real-time bidirectional chat.
Clients connect once, then send/receive JSON messages.
"""

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.core.security import verify_access_token
from app.schemas.conversation import ConversationCreate
from app.services.ai.rag_pipeline import RAGPipeline
from app.services.legal.conversation_service import ConversationService

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id] = ws
        logger.info(f"WS connected: user_id={user_id}")

    def disconnect(self, user_id: str) -> None:
        self._connections.pop(user_id, None)
        logger.info(f"WS disconnected: user_id={user_id}")

    async def send(self, user_id: str, data: dict[str, Any]) -> None:
        ws = self._connections.get(user_id)
        if ws:
            await ws.send_text(json.dumps(data))


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, token: str | None = None):
    # Authenticate via query-param token
    user_id: str | None = None
    if token:
        try:
            user_id = verify_access_token(token)
        except ValueError:
            await websocket.close(code=4001, reason="Invalid token")
            return
    else:
        await websocket.close(code=4001, reason="Token required")
        return

    await manager.connect(user_id, websocket)
    rag = RAGPipeline()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(user_id, {"type": "error", "error": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await manager.send(user_id, {"type": "pong"})

            elif msg_type == "chat":
                query = msg.get("message", "").strip()
                conversation_id = msg.get("conversation_id")

                if not query:
                    continue

                # Stream back chunks
                await manager.send(
                    user_id, {"type": "start", "conversation_id": conversation_id}
                )

                full_answer = ""
                try:
                    async with AsyncSessionLocal() as db:
                        conv_svc = ConversationService(db)
                        if conversation_id:
                            import uuid

                            conv = await conv_svc.get(
                                uuid.UUID(conversation_id), uuid.UUID(user_id)
                            )
                        else:
                            conv = await conv_svc.create(
                                ConversationCreate(), uuid.UUID(user_id)
                            )
                            conversation_id = str(conv.id)

                        history = await conv_svc.get_messages(conv.id, limit=10)
                        await conv_svc.add_message(conv.id, role="user", content=query)

                    async for chunk in rag.stream(
                        query=query,
                        conversation_history=history,
                        top_k=msg.get("top_k", 5),
                    ):
                        payload = chunk.model_dump()
                        payload["conversation_id"] = conversation_id
                        await manager.send(user_id, payload)
                        if chunk.type == "text":
                            full_answer += chunk.content or ""

                    # Persist answer
                    async with AsyncSessionLocal() as db:
                        conv_svc = ConversationService(db)
                        import uuid

                        await conv_svc.add_message(
                            uuid.UUID(conversation_id),
                            role="assistant",
                            content=full_answer,
                        )

                except Exception as e:
                    logger.error(f"WS chat error: {e}")
                    await manager.send(user_id, {"type": "error", "error": str(e)})

            else:
                await manager.send(
                    user_id, {"type": "error", "error": f"Unknown type: {msg_type}"}
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
