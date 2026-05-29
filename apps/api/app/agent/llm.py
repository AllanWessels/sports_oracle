"""Claude model factories."""

from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.config import get_settings


# NOTE: `temperature` is deprecated on newer Claude models (e.g. opus-4-8) and
# the API rejects it, so we don't pass it — models use their default.

@lru_cache
def router_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model_router, api_key=s.anthropic_api_key)


@lru_cache
def synth_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model_synth, api_key=s.anthropic_api_key, streaming=True)


@lru_cache
def predict_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model_predict, api_key=s.anthropic_api_key)


@lru_cache
def eval_model() -> ChatAnthropic:
    """Judge model for RAGAS; used by the async worker."""
    s = get_settings()
    return ChatAnthropic(model=s.model_eval, api_key=s.anthropic_api_key)
