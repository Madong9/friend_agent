"""DeepSeek/OpenAI-compatible provider resilience: fallback and production guard."""

import pytest

from backend.app.config import Settings
from backend.app.agents import CampusSocialAgent, TraceStore
from backend.app.llm import (
    MockLLMProvider,
    OpenAICompatibleProvider,
    ResilientLLMProvider,
)
from backend.app.schemas.agent import SocialIntent


class FailingProvider(OpenAICompatibleProvider):
    async def structured(self, prompt: str, output_schema):
        raise RuntimeError("api key invalid")


async def test_failing_provider_falls_back_to_mock_and_marks_label():
    provider = ResilientLLMProvider(FailingProvider("http://x", "k", "m"), True)
    result = await provider.structured("找周六下午羽毛球搭子", SocialIntent)
    assert isinstance(result, SocialIntent)
    assert result.activity == "羽毛球"
    assert provider.provider_label.endswith(":fallback")


async def test_failing_provider_raises_without_fallback():
    provider = ResilientLLMProvider(FailingProvider("http://x", "k", "m"), False)
    with pytest.raises(RuntimeError, match="api key invalid"):
        await provider.structured("找搭子", SocialIntent)


async def test_healthy_provider_keeps_primary_label():
    provider = ResilientLLMProvider(MockLLMProvider(), True)
    result = await provider.structured("找周六下午羽毛球搭子", SocialIntent)
    assert result.activity == "羽毛球"
    assert provider.provider_label == "mock"


def test_production_disables_mock_fallback():
    settings = Settings(
        app_env="production",
        llm_fallback_to_mock=True,
        jwt_secret="production-secret-that-is-long-enough-32",
    )
    with pytest.raises(ValueError, match="LLM_FALLBACK_TO_MOCK"):
        settings.validate_runtime()


async def test_agent_trace_records_the_provider_that_actually_answered(
    db, sample_users
):
    provider = ResilientLLMProvider(FailingProvider("http://x", "k", "m"), True)
    result = await CampusSocialAgent(db, provider).run(
        "a", "找周六下午羽毛球搭子，最好西区", limit=2
    )
    trace = TraceStore(db).get(result["session_id"])
    parse_entry = next(item for item in trace.entries if item.action == "parse_intent")
    assert parse_entry.tool == "openai_compatible:fallback"
    assert parse_entry.metadata["provider"] == "openai_compatible:fallback"
