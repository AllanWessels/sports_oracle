"""Persist a finished conversation turn to Postgres via the shared db library."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def persist_turn(
    conversation_id: Optional[str],
    user_message: str,
    answer: str,
    intent: str,
    citations: list,
    prediction=None,
) -> dict:
    """Save the user + assistant messages, citations, and any prediction.

    Returns {conversation_id, message_id}. Degrades to a generated, unsaved id
    pair if the DB is unavailable so the stream can still complete.
    """
    try:
        from sports_oracle_db import repository as repo  # type: ignore
        from sports_oracle_db.session import get_session  # type: ignore

        async with get_session() as session:
            if not conversation_id:
                conv = await repo.create_conversation(session, title=user_message[:60])
                conversation_id = str(conv.id)
            await repo.add_message(session, conversation_id, role="user", content=user_message)
            msg = await repo.add_message(
                session, conversation_id, role="assistant", content=answer, intent=intent
            )
            if citations:
                await repo.add_citations(session, str(msg.id), citations)
            if prediction is not None:
                await repo.add_prediction(session, str(msg.id), prediction)
            await repo.touch_conversation(session, conversation_id)
            await session.commit()
            return {"conversation_id": conversation_id, "message_id": str(msg.id)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Persistence unavailable, continuing without saving: %s", exc)
        import uuid

        return {
            "conversation_id": conversation_id or str(uuid.uuid4()),
            "message_id": str(uuid.uuid4()),
        }
