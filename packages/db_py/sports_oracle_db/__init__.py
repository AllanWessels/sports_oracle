"""Sports Oracle DB — async Postgres persistence library.

Public API
----------
Models:
    Base, Conversation, Message, Citation, Prediction, SemanticCacheMeta

Session / engine:
    get_engine, get_session_factory, get_session, init_models, drop_models,
    reset_engine

Repository — conversations:
    create_conversation, get_conversation, list_conversations, touch_conversation

Repository — messages:
    add_message, get_messages

Repository — citations:
    add_citations, citation_to_dto

Repository — predictions:
    add_prediction, prediction_to_dto

Repository — semantic cache:
    record_cache_meta, bump_cache_hit, find_fresh_cache_meta
"""

from sports_oracle_db.models import (
    Base,
    Citation,
    Conversation,
    EvalTrace,
    Message,
    Prediction,
    SemanticCacheMeta,
)
from sports_oracle_db.repository import (
    add_citations,
    add_message,
    add_prediction,
    bump_cache_hit,
    citation_to_dto,
    create_conversation,
    find_fresh_cache_meta,
    get_conversation,
    get_messages,
    get_unjudged_traces,
    insert_trace,
    list_conversations,
    list_traces,
    prediction_to_dto,
    record_cache_meta,
    touch_conversation,
    trace_to_dict,
    update_trace_scores,
)
from sports_oracle_db.session import (
    drop_models,
    get_engine,
    get_session,
    get_session_factory,
    init_models,
    reset_engine,
)

__all__ = [
    # models
    "Base",
    "Conversation",
    "Message",
    "Citation",
    "Prediction",
    "SemanticCacheMeta",
    "EvalTrace",
    # session
    "get_engine",
    "get_session_factory",
    "get_session",
    "init_models",
    "drop_models",
    "reset_engine",
    # repository — conversations
    "create_conversation",
    "get_conversation",
    "list_conversations",
    "touch_conversation",
    # repository — messages
    "add_message",
    "get_messages",
    # repository — citations
    "add_citations",
    "citation_to_dto",
    # repository — predictions
    "add_prediction",
    "prediction_to_dto",
    # repository — semantic cache
    "record_cache_meta",
    "bump_cache_hit",
    "find_fresh_cache_meta",
    # repository — eval traces
    "insert_trace",
    "get_unjudged_traces",
    "update_trace_scores",
    "list_traces",
    "trace_to_dict",
]
