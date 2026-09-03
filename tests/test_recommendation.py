import pytest

from backend.app.agents import CampusSocialAgent, TraceStore
from backend.app.llm import MockLLMProvider


@pytest.mark.asyncio
async def test_recommendation_and_trace(db, sample_users):
    result = await CampusSocialAgent(db, MockLLMProvider()).run(
        "a", "帮我找周六下午一起打羽毛球的人，最好西区", limit=3
    )
    assert result["goal"] == "find_activity_partner"
    assert result["matches"][0]["id"] == "b"
    assert "羽毛球" in result["suggested_icebreakers"][0]
    trace = TraceStore(db).get(result["session_id"])
    assert trace is not None
    assert [entry.step for entry in trace.entries] == list(range(1, 10))
    assert all(entry.status == "success" for entry in trace.entries)


@pytest.mark.asyncio
async def test_trace_can_be_disabled(db, sample_users):
    result = await CampusSocialAgent(db, MockLLMProvider(), trace_enabled=False).run(
        "a", "找羽毛球搭子"
    )
    assert TraceStore(db).get(result["session_id"]) is None
