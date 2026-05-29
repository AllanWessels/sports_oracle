"""Conversation history endpoints (read-only)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/conversations")
async def list_conversations() -> list[dict]:
    try:
        from sports_oracle_db import repository as repo  # type: ignore
        from sports_oracle_db.session import get_session  # type: ignore

        async with get_session() as session:
            convs = await repo.list_conversations(session)
            return [
                {"id": str(c.id), "title": c.title, "updated_at": c.updated_at.isoformat()}
                for c in convs
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_conversations unavailable: %s", exc)
        return []


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str) -> dict:
    try:
        from sports_oracle_db import repository as repo  # type: ignore
        from sports_oracle_db.session import get_session  # type: ignore

        async with get_session() as session:
            messages = await repo.get_messages(session, conversation_id)
            return {
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "intent": m.intent,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ]
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_messages unavailable: %s", exc)
        return {"messages": []}
