import pytest

from backend.app.agents import CampusSocialAgent
from backend.app.llm import MockLLMProvider
from backend.app.memory import MemoryManager
from backend.app.services import SocialService


@pytest.mark.asyncio
async def test_end_to_end_feedback_changes_next_recommendation(db, sample_users):
    agent = CampusSocialAgent(db, MockLLMProvider())
    first = await agent.run("a", "找周六下午的羽毛球搭子，最好西区", limit=1)
    passed_id = first["matches"][0]["id"]
    SocialService(db).record_feedback("a", passed_id, "PASS")
    assert passed_id in MemoryManager(db).get_recent_candidates("a")
    second = await agent.run("a", "找周六下午的羽毛球搭子，最好西区", limit=3)
    assert passed_id not in [item["id"] for item in second["matches"]]
