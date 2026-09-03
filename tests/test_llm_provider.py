import json
import logging

import httpx
import pytest

from backend.app.config import Settings
from backend.app.llm import (
    LLMProviderError,
    OpenAICompatibleProvider,
    ResilientLLMProvider,
    create_llm_provider,
)
from backend.app.schemas.agent import SocialIntent


def test_llm_timeout_defaults_to_30_seconds(monkeypatch):
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().llm_timeout_seconds == 30.0


def test_llm_timeout_can_be_overridden_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    assert Settings.from_env().llm_timeout_seconds == 12.5


@pytest.mark.parametrize("timeout", [0, -0.01])
def test_llm_timeout_must_be_positive(timeout):
    settings = Settings(llm_timeout_seconds=timeout)
    with pytest.raises(ValueError, match="LLM_TIMEOUT_SECONDS must be positive"):
        settings.validate_runtime()


def test_factory_passes_configured_timeout_to_openai_provider():
    settings = Settings(
        llm_provider="openai_compatible",
        llm_base_url="https://llm.example/v1",
        llm_api_key="test-key",
        llm_model="test-model",
        llm_timeout_seconds=7.25,
        llm_fallback_to_mock=False,
    )
    provider = create_llm_provider(settings)

    assert isinstance(provider, ResilientLLMProvider)
    assert isinstance(provider.primary, OpenAICompatibleProvider)
    assert provider.primary.timeout == 7.25


@pytest.mark.asyncio
async def test_openai_compatible_provider_uses_structured_output():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["name"] == "SocialIntent"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "goal": "find_activity_partner",
                                    "activity": "羽毛球",
                                    "availability": ["周六下午"],
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(
        "https://llm.example/v1",
        "test-key",
        "test-model",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.structured("找羽毛球搭子", SocialIntent)
    assert result.activity == "羽毛球"
    assert result.availability == ["周六下午"]


def test_openai_compatible_provider_requires_endpoint_and_model():
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        OpenAICompatibleProvider("", "", "")


@pytest.mark.parametrize(
    ("exception_class", "exception_name"),
    [
        (httpx.ConnectTimeout, "ConnectTimeout"),
        (httpx.ReadTimeout, "ReadTimeout"),
    ],
)
@pytest.mark.asyncio
async def test_timeout_logs_safe_diagnostics(
    exception_class, exception_name, caplog
):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise exception_class("sensitive-exception-message", request=request)

    provider = OpenAICompatibleProvider(
        "https://llm.example/v1",
        "sk-private-test-key",
        "glm-diagnostic-model",
        transport=httpx.MockTransport(handler),
    )
    prompt = "sensitive-user-prompt"

    with caplog.at_level(logging.WARNING, logger="backend.app.llm.openai_compatible"):
        with pytest.raises(LLMProviderError, match="unusable SocialIntent"):
            await provider.structured(prompt, SocialIntent)

    log_output = caplog.text
    assert f"exception_type={exception_name}" in log_output
    assert "elapsed_seconds=" in log_output
    assert "hostname=llm.example" in log_output
    assert "model=glm-diagnostic-model" in log_output
    assert "status_code=none" in log_output
    assert "sk-private-test-key" not in log_output
    assert prompt not in log_output
    assert "sensitive-exception-message" not in log_output


@pytest.mark.asyncio
async def test_deepseek_chat_completions_uses_json_object_mode():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "JSON Schema" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "goal": "find_activity_partner",
                                    "activity": "羽毛球",
                                }
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(
        "https://api.deepseek.com",
        "test-key",
        "deepseek-chat",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.structured("找羽毛球搭子", SocialIntent)
    assert result.activity == "羽毛球"


@pytest.mark.asyncio
async def test_glm_auto_mode_uses_json_object_behind_custom_gateway():
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "glm-5.3-flash"
        assert payload["response_format"] == {"type": "json_object"}
        assert "JSON Schema" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "goal": "find_study_partner",
                                    "activity": "自习",
                                    "campus": "西区",
                                    "hard_constraints": ["campus"],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(
        "https://api.llm.ustc.edu.cn/v1",
        "test-key",
        "glm-5.3-flash",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.structured("请返回 JSON", SocialIntent)
    assert result.goal == "find_study_partner"


@pytest.mark.asyncio
async def test_provider_wraps_empty_or_invalid_structured_output():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    provider = OpenAICompatibleProvider(
        "https://llm.example/v1",
        "test-key",
        "test-model",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMProviderError, match="unusable SocialIntent"):
        await provider.structured("找搭子", SocialIntent)
