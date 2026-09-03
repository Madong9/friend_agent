import pytest

from backend.app.tools.conversation_tool import ConversationTool, ConversationToolInput
from backend.app.tools.activity_tool import ActivityTool, ActivityToolInput
from backend.app.tools.matching_tool import MatchingTool, MatchingToolInput
from backend.app.tools.memory_tool import MemoryTool, MemoryToolInput
from backend.app.tools.profile_tool import ProfileTool, ProfileToolInput
from backend.app.tools.safety_tool import SafetyTool, SafetyToolInput
from backend.app.tools.privacy import public_user
from backend.app.models import Activity
from backend.app.services import SocialService


@pytest.mark.asyncio
async def test_agent_tools(db, sample_users):
    user, candidate, _ = sample_users
    profile = await ProfileTool(db).execute(
        ProfileToolInput(action="load_profile", user_id=user.id)
    )
    assert profile["nickname"] == "甲"

    updated = await ProfileTool(db).execute(
        ProfileToolInput(
            action="update_profile",
            user_id=user.id,
            updates={"social_style": "慢热"},
        )
    )
    assert updated["social_style"] == "慢热"

    found = await MatchingTool(db).execute(
        MatchingToolInput(action="search_candidates", user_id=user.id, intent={})
    )
    assert candidate.id in found["candidate_ids"]

    safety = await SafetyTool(db).execute(
        SafetyToolInput(
            action="check_message", message="加我做刷单，稳赚 https://bad.example"
        )
    )
    assert safety["safe"] is False
    assert "suspected_fraud" in safety["risk_signals"]

    spoofed_link = await SafetyTool(db).execute(
        SafetyToolInput(
            action="check_message",
            message="这个地址看起来像校内站 https://campus.example.evil.test/path",
        )
    )
    assert "external_link" in spoofed_link["risk_signals"]

    campus_link = await SafetyTool(db).execute(
        SafetyToolInput(
            action="check_message", message="活动页 https://events.campus.example/path"
        )
    )
    assert campus_link["safe"] is True

    memory_tool = MemoryTool(db)
    session = await memory_tool.execute(
        MemoryToolInput(
            action="update_memory",
            user_id=user.id,
            session_id="tool-session",
            values={"last_goal": "find_activity_partner"},
        )
    )
    assert session["last_goal"] == "find_activity_partner"

    db.add(
        Activity(
            id="activity-test",
            name="羽毛球约球",
            campus="西区",
            location="体育馆",
            time="周六下午",
            tags=["羽毛球"],
            capacity=12,
            public=True,
        )
    )
    db.commit()
    activities = await ActivityTool(db).execute(
        ActivityToolInput(campus="西区", tag="羽毛球")
    )
    assert activities[0]["id"] == "activity-test"

    db.add(
        Activity(
            id="private-activity",
            name="非公开羽毛球活动",
            campus="西区",
            location="内部场地",
            time="周六下午",
            tags=["羽毛球"],
            capacity=5,
            public=False,
        )
    )
    db.commit()
    activities = await ActivityTool(db).execute(
        ActivityToolInput(campus="西区", tag="羽毛球")
    )
    assert "private-activity" not in {item["id"] for item in activities}

    icebreaker = await ConversationTool().execute(
        ConversationToolInput(
            action="generate_icebreaker",
            requester=profile,
            candidate={"interests": candidate.interests, "campus": candidate.campus},
            intent={"activity": "羽毛球"},
        )
    )
    assert "羽毛球" in icebreaker["icebreaker"]

    topics = await ConversationTool().execute(
        ConversationToolInput(
            action="generate_topics",
            requester=profile,
            candidate={
                "interests": candidate.interests,
                "campus": candidate.campus,
            },
            intent={"activity": "羽毛球"},
        )
    )
    assert topics["topics"]
    assert set(topics["topics"]) <= set(profile["interests"])

    with pytest.raises(ValueError, match="cannot be updated"):
        await ProfileTool(db).execute(
            ProfileToolInput(
                action="update_profile",
                user_id=user.id,
                updates={"school_email": "leak@ustc.edu.cn"},
            )
        )

    visible = public_user(candidate)
    assert {
        "school_email",
        "school_uid",
        "school_display_name",
        "password_hash",
        "verified",
    }.isdisjoint(visible)

    SocialService(db).block_user(user.id, candidate.id)
    block_safety = await SafetyTool(db).execute(
        SafetyToolInput(
            action="check_block", user_id=user.id, candidate_id=candidate.id
        )
    )
    assert block_safety == {"safe": False, "reason": "blocked_relation"}
