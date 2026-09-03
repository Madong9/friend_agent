import pytest

from backend.app.llm import MockLLMProvider
from backend.app.services.parsers import parse_social_intent


@pytest.mark.asyncio
async def test_intent_parser():
    result = await parse_social_intent(
        "找几个周六下午能一起打羽毛球的人，最好西区。", MockLLMProvider()
    )
    assert result.goal == "find_activity_partner"
    assert result.activity == "羽毛球"
    assert result.availability == ["周六下午"]
    assert result.campus == "西区"
    assert result.soft_preferences == ["campus"]


@pytest.mark.asyncio
async def test_postgraduate_review_intent_is_normalized():
    result = await parse_social_intent(
        "我要准备考研，你帮我找一个在西区一起复习的搭子",
        MockLLMProvider(),
    )
    assert result.goal == "find_study_partner"
    assert result.activity == "自习"
    assert result.campus == "西区"
    assert result.hard_constraints == ["campus"]
    assert "campus" not in result.soft_preferences
