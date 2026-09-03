import pytest
from fastapi.testclient import TestClient

from backend.app.agents import CampusSocialAgent, TraceStore
from backend.app.agents.router import AgentTask, TaskRouter
from backend.app.database import get_db
from backend.app.llm import MockLLMProvider
from backend.app.main import app
from backend.app.memory import MemoryManager
from backend.app.models import Activity, Notification, PartnerRequest, User
from backend.app.schemas.agent import SocialIntent


class ClarificationConversationLLM:
    provider_label = "scripted-multiturn"

    def __init__(self):
        self.prompts = []

    async def structured(self, prompt, output_schema):
        assert output_schema is SocialIntent
        self.prompts.append(prompt)
        if "用户输入：周六下午羽毛球，西区" in prompt:
            return SocialIntent(
                goal="find_activity_partner",
                campus="西区",
                soft_preferences=["campus"],
            )
        if "用户输入：跑步" in prompt:
            return SocialIntent(goal="find_activity_partner", activity="跑步")
        if "用户输入：周五晚上" in prompt:
            return SocialIntent(
                goal="find_interest_friend", availability=["周五晚上"]
            )
        raise AssertionError(f"confirmation must not be reparsed by LLM: {prompt}")


class NovelActivityLLM:
    provider_label = "scripted-novel-activity"

    async def structured(self, prompt, output_schema):
        assert output_schema is SocialIntent
        availability = ["周五晚上"] if "周五晚上" in prompt else ["周六下午"]
        return SocialIntent(
            goal="find_activity_partner",
            activity="飞盘",
            availability=availability,
        )


@pytest.mark.asyncio
async def test_agent_clarifies_and_merges_the_next_turn(db, sample_users):
    agent = CampusSocialAgent(db, MockLLMProvider())

    first = await agent.run("a", "找羽毛球搭子")
    assert first["response_type"] == "clarification"
    assert first["needs_clarification"] is True
    assert first["intent"]["activity"] == "羽毛球"
    assert first["plan"][-1]["action"] == "ask_clarification"

    second = await agent.run("a", "周六下午", session_id=first["session_id"])
    assert second["response_type"] == "recommendation"
    assert second["intent"]["activity"] == "羽毛球"
    assert second["intent"]["availability"] == ["周六下午"]
    assert second["matches"][0]["id"] == "b"

    trace = TraceStore(db).get(first["session_id"])
    assert trace is not None
    assert [entry.step for entry in trace.entries] == list(range(1, 14))
    assert "merge_clarification" in [entry.action for entry in trace.entries]


@pytest.mark.asyncio
async def test_agent_replans_and_only_relaxes_after_confirmation(db, sample_users):
    agent = CampusSocialAgent(db, MockLLMProvider())

    first = await agent.run("a", "找周六下午羽毛球搭子，只能东区")
    assert first["response_type"] == "no_results"
    assert first["needs_clarification"] is True
    assert first["plan"][-2]["action"] == "observe_no_candidates"
    assert first["plan"][-1]["action"] == "request_constraint_relaxation"

    second = await agent.run("a", "可以放宽", session_id=first["session_id"])
    assert second["response_type"] == "recommendation"
    assert "campus" not in second["intent"]["hard_constraints"]
    assert second["matches"][0]["id"] == "b"


@pytest.mark.parametrize("reply", ["是", "是的", "可以", "好", "同意放宽"])
def test_router_understands_affirmative_relaxation_replies(reply):
    decision = TaskRouter().route(reply, {"pending_relaxation": "availability"})
    assert decision.task == AgentTask.CONFIRM_RELAXATION


@pytest.mark.parametrize("reply", ["不是", "不可以", "不同意", "不要放宽"])
def test_router_does_not_treat_negative_replies_as_confirmation(reply):
    decision = TaskRouter().route(reply, {"pending_relaxation": "availability"})
    assert decision.task == AgentTask.FIND_PARTNER


def test_multiturn_availability_relaxation_restores_session_without_reasking_activity(
    db, sample_users, auth_headers, monkeypatch
):
    # The fourth turn only relaxes time. Keep an exact running candidate whose
    # original time conflicts, so the regression cannot pass by silently
    # broadening the requested activity too.
    sample_users[1].activities = [*sample_users[1].activities, "跑步"]
    db.commit()
    scripted_llm = ClarificationConversationLLM()
    monkeypatch.setattr(
        "backend.app.agents.campus_agent.create_llm_provider",
        lambda: scripted_llm,
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = client.post(
                "/agent/chat",
                json={"message": "周六下午羽毛球，西区"},
                headers=auth_headers("a"),
            )
            assert first.status_code == 200
            first_payload = first.json()
            session_id = first_payload["session_id"]
            assert first_payload["response_type"] == "clarification"
            assert "哪一类搭子" in first_payload["message"]

            second = client.post(
                "/agent/chat",
                json={"message": "跑步", "session_id": session_id},
                headers=auth_headers("a"),
            )
            assert second.status_code == 200
            second_payload = second.json()
            assert second_payload["session_id"] == session_id
            assert second_payload["response_type"] == "clarification"
            assert second_payload["intent"]["activity"] == "跑步"
            assert "什么时间" in second_payload["message"]

            third = client.post(
                "/agent/chat",
                json={"message": "周五晚上", "session_id": session_id},
                headers=auth_headers("a"),
            )
            assert third.status_code == 200
            third_payload = third.json()
            assert third_payload["session_id"] == session_id
            assert third_payload["response_type"] == "no_results"
            assert third_payload["intent"]["activity"] == "跑步"
            assert third_payload["intent"]["availability"] == ["周五晚上"]
            assert "放宽可用时间" in third_payload["message"]

            pending = MemoryManager(db).get_session(session_id)
            assert pending["intent"]["activity"] == "跑步"
            assert pending["intent"]["availability"] == ["周五晚上"]
            assert pending["pending_relaxation"] == "availability"

            fourth = client.post(
                "/agent/chat",
                json={"message": "是", "session_id": session_id},
                headers=auth_headers("a"),
            )
            assert fourth.status_code == 200
            fourth_payload = fourth.json()
            assert fourth_payload["session_id"] == session_id
            assert fourth_payload["response_type"] == "recommendation"
            assert fourth_payload["intent"]["activity"] == "跑步"
            assert fourth_payload["intent"]["availability"] == ["周五晚上"]
            assert fourth_payload["matches"]
            assert "哪一类搭子" not in fourth_payload["message"]

            restored = MemoryManager(db).get_session(session_id)
            assert restored["turn_count"] == 4
            assert restored["intent"]["activity"] == "跑步"
            assert restored["intent"]["availability"] == ["周五晚上"]
            assert restored["pending_relaxation"] is None
            assert "availability" in restored["relaxed_slots"]
            assert len(scripted_llm.prompts) == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_novel_activity_is_remembered_and_discoverable_by_later_user(
    db, sample_users
):
    initial_activity_count = db.query(Activity).count()
    provider = NovelActivityLLM()

    first = await CampusSocialAgent(db, provider).run(
        "a", "找周五晚上飞盘搭子"
    )
    assert first["response_type"] == "no_results"
    assert first["intent"]["activity"] == "飞盘"
    assert "飞盘" in db.get(User, "a").activities
    assert db.query(Activity).count() == initial_activity_count

    second = await CampusSocialAgent(db, provider).run(
        "b", "找周六下午飞盘搭子"
    )
    assert "飞盘" in db.get(User, "b").activities
    assert second["response_type"] == "recommendation"
    assert second["matches"][0]["id"] == "a"
    assert second["matches"][0]["score_breakdown"]["activity"] == 1.0

    waiting = db.query(PartnerRequest).filter_by(user_id="a").one()
    assert waiting.normalized_activity == "飞盘"
    notification = db.query(Notification).filter_by(user_id="a").one()
    assert notification.kind == "NEW_PARTNER_CANDIDATE"
    assert notification.payload["source_session_id"] == second["session_id"]

    trace = TraceStore(db).get(first["session_id"])
    assert trace is not None
    parse_entry = next(item for item in trace.entries if item.action == "parse_intent")
    assert parse_entry.metadata["activity_preference_added"] == "飞盘"


@pytest.mark.asyncio
async def test_agent_routes_activity_profile_and_explanation_tasks(db, sample_users):
    db.add(
        Activity(
            id="act-1",
            name="西区周末羽毛球局",
            campus="西区",
            location="风雨操场",
            time="周六下午",
            tags=["羽毛球"],
            capacity=16,
        )
    )
    db.commit()
    agent = CampusSocialAgent(db, MockLLMProvider())

    activity = await agent.run("a", "西区有什么活动")
    assert activity["response_type"] == "activities"
    assert activity["activities"][0]["id"] == "act-1"
    assert [item["action"] for item in activity["plan"]] == [
        "safety_check_message",
        "parse_intent",
        "search_activities",
        "generate_activity_response",
    ]

    updated = await agent.run("a", "更新画像：我喜欢跑步，周日下午有空")
    assert updated["response_type"] == "profile_updated"
    assert updated["profile"]["interests"] == ["跑步"]
    assert updated["profile"]["availability"] == ["周日下午"]

    matched = await agent.run("a", "找周六下午羽毛球搭子")
    explained = await agent.run("a", "为什么推荐乙", session_id=matched["session_id"])
    assert explained["response_type"] == "explanation"
    assert "推荐乙" in explained["message"]
    assert "羽毛球" in explained["message"]
    assert "0.00" not in explained["message"]


@pytest.mark.asyncio
async def test_agent_session_cannot_be_continued_by_another_user(db, sample_users):
    agent = CampusSocialAgent(db, MockLLMProvider())
    first = await agent.run("a", "找羽毛球搭子")

    with pytest.raises(PermissionError):
        await agent.run("b", "周六下午", session_id=first["session_id"])


@pytest.mark.asyncio
async def test_postgraduate_review_request_uses_profile_time_and_hard_campus(
    db, sample_users
):
    db.add(
        User(
            id="study-west",
            nickname="研友",
            school_email="study-west@ustc.edu.cn",
            school="中国科学技术大学",
            campus="西区",
            grade="大四",
            major="数学",
            social_goals=["学习搭子"],
            interests=["阅读"],
            activities=["自习"],
            availability=["周六下午"],
            verified=True,
        )
    )
    db.commit()

    result = await CampusSocialAgent(db, MockLLMProvider()).run(
        "a", "我要准备考研，你帮我找一个在西区一起复习的搭子"
    )

    assert result["response_type"] == "recommendation"
    assert result["goal"] == "find_study_partner"
    assert result["intent"]["activity"] == "自习"
    assert result["intent"]["campus"] == "西区"
    assert "campus" in result["intent"]["hard_constraints"]
    assert result["matches"][0]["id"] == "study-west"


def test_multiturn_session_is_wired_through_http_api(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = client.post(
                "/agent/chat",
                json={"message": "找羽毛球搭子"},
                headers=auth_headers("a"),
            )
            assert first.status_code == 200
            first_payload = first.json()
            assert first_payload["response_type"] == "clarification"

            forbidden = client.post(
                "/agent/chat",
                json={
                    "message": "周六下午",
                    "session_id": first_payload["session_id"],
                },
                headers=auth_headers("b"),
            )
            assert forbidden.status_code == 403

            second = client.post(
                "/agent/chat",
                json={
                    "message": "周六下午",
                    "session_id": first_payload["session_id"],
                },
                headers=auth_headers("a"),
            )
            assert second.status_code == 200
            assert second.json()["matches"][0]["id"] == "b"
    finally:
        app.dependency_overrides.clear()
