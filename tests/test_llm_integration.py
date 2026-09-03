"""Optional integration tests against the real DeepSeek API.

Run manually with a real key in .env (never hard-code keys here):

    RUN_LLM_INTEGRATION=1 pytest tests/test_llm_integration.py -v

普通 pytest 不运行本文件，也不消耗真实 API 额度。
"""

import os

import pytest

from backend.app.config import get_settings
from backend.app.llm.factory import create_llm_provider
from backend.app.schemas.agent import SocialIntent
from backend.app.schemas.user import ProfileParseResult
from backend.app.services.parsers import parse_profile_text, parse_social_intent

requires_real_llm = pytest.mark.skipif(
    os.getenv("RUN_LLM_INTEGRATION") != "1"
    or not get_settings().llm_api_key
    or get_settings().llm_provider == "mock",
    reason="RUN_LLM_INTEGRATION=1 and a real LLM_API_KEY are required",
)


@requires_real_llm
async def test_real_llm_parses_social_intent():
    provider = create_llm_provider()
    intent = await parse_social_intent(
        "帮我找几个周六下午能一起打羽毛球的人，最好在西区，水平休闲一点。",
        provider,
    )
    assert isinstance(intent, SocialIntent)
    assert intent.goal == "find_activity_partner"
    assert intent.activity == "羽毛球"
    assert intent.availability
    assert intent.campus in {"西区", "west"}


@requires_real_llm
async def test_real_llm_parses_profile_text():
    provider = create_llm_provider()
    parsed = await parse_profile_text(
        "我研一，喜欢跑步和摄影，平时比较慢热，晚上比较有时间。",
        provider,
    )
    assert isinstance(parsed, ProfileParseResult)
    assert parsed.grade is not None
    assert {"跑步", "摄影"} & set(parsed.interests)


@requires_real_llm
async def test_real_llm_invalid_key_falls_back_in_development(monkeypatch):
    settings = get_settings()
    if settings.app_env == "production":
        pytest.skip("fallback is disabled in production by design")
    from backend.app.llm import OpenAICompatibleProvider, ResilientLLMProvider

    provider = ResilientLLMProvider(
        OpenAICompatibleProvider(
            settings.llm_base_url,
            "sk-invalid-key-for-test",
            settings.llm_model,
            timeout=15.0,
        ),
        allow_fallback=True,
    )
    intent = await parse_social_intent("周六下午打羽毛球", provider)
    assert intent.activity == "羽毛球"
    assert provider.provider_label.endswith(":fallback")
