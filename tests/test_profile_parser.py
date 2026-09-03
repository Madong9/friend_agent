import pytest

from backend.app.llm import MockLLMProvider
from backend.app.services.parsers import parse_profile_text


@pytest.mark.asyncio
async def test_profile_parser():
    result = await parse_profile_text(
        "我研一，喜欢跑步和摄影，平时比较慢热，晚上比较有时间。", MockLLMProvider()
    )
    assert result.grade == "研一"
    assert result.interests == ["跑步", "摄影"]
    assert result.social_style == "慢热"
    assert "晚上" in result.availability
