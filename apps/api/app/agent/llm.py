"""Claude model factories."""

from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from app.config import get_settings


@lru_cache
def router_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model_router, api_key=s.anthropic_api_key, temperature=0)


@lru_cache
def synth_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(
        model=s.model_synth, api_key=s.anthropic_api_key, temperature=0.3, streaming=True
    )


@lru_cache
def predict_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model_predict, api_key=s.anthropic_api_key, temperature=0.2)
