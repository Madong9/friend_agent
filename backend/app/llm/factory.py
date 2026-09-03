from __future__ import annotations

from ..config import Settings, get_settings
from .base import LLMProvider
from .mock import MockLLMProvider
from .openai_compatible import OpenAICompatibleProvider
from .resilient import ResilientLLMProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider.lower() == "mock":
        return MockLLMProvider()
    if settings.llm_provider.lower() in {
        "openai",
        "openai_compatible",
        "qwen",
        "deepseek",
    }:
        primary = OpenAICompatibleProvider(
            settings.llm_base_url,
            settings.llm_api_key,
            settings.llm_model,
            timeout=settings.llm_timeout_seconds,
            response_format_mode=settings.llm_response_format,
            trust_env=settings.outbound_http_trust_env,
        )
        return ResilientLLMProvider(primary, settings.llm_fallback_to_mock)
    raise ValueError(f"unknown LLM_PROVIDER: {settings.llm_provider}")
