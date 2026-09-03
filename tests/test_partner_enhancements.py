from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.main import app
from backend.app.matching.scorer import personality_compatibility, score_candidate
from backend.app.models import Notification, PartnerRequest
from backend.app.services.parsers import normalize_availability
from backend.app.services.partner_loop import PartnerLoopService


def _client_for(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_personality_analysis_requires_consent_and_can_be_deleted(
    db, sample_users, auth_headers
):
    try:
        with _client_for(db) as client:
            denied = client.post(
                "/users/me/personality/analyze",
                json={
                    "text": "我比较慢热，喜欢提前约好，两三个人活动最舒服。",
                    "consent": False,
                },
                headers=auth_headers("a"),
            )
            assert denied.status_code == 400

            analyzed = client.post(
                "/users/me/personality/analyze",
                json={
                    "text": "我比较慢热，喜欢提前约好，两三个人活动最舒服。",
                    "consent": True,
                },
                headers=auth_headers("a"),
            )
            assert analyzed.status_code == 200
            assert analyzed.json()["traits"]["energy"] == "quiet"
            assert analyzed.json()["traits"]["planning"] == "planned"

            me = client.get("/users/me", headers=auth_headers("a")).json()
            assert me["personality_consent"] is True
            assert me["personality_summary"]

            cleared = client.delete(
                "/users/me/personality", headers=auth_headers("a")
            )
            assert cleared.status_code == 204
            me = client.get("/users/me", headers=auth_headers("a")).json()
            assert me["personality_consent"] is False
            assert me["personality_traits"] == {}
            assert me["personality_summary"] == ""
    finally:
        app.dependency_overrides.clear()


def test_personality_is_optional_and_bounded_in_matching(sample_users):
    user, candidate, _ = sample_users
    intent = {"activity": "羽毛球", "availability": ["周六下午"]}
    original = score_candidate(user, candidate, intent)

    user.personality_traits = {
        "energy": "quiet",
        "planning": "planned",
        "communication": "reserved",
        "group_preference": "small_group",
        "connection_pace": "slow_warmup",
    }
    candidate.personality_traits = dict(user.personality_traits)
    enriched = score_candidate(user, candidate, intent)

    assert original.features["personality"] == 0.5
    assert personality_compatibility(user.personality_traits, {}) is None
    assert enriched.features["personality"] == 1.0
    assert 0 <= enriched.total - original.total <= 0.1
    assert "公开社交风格较合拍" in enriched.reasons


def test_social_features_can_require_campus_verification(
    db, sample_users, auth_headers, monkeypatch
):
    sample_users[0].campus_verified = False
    db.commit()
    monkeypatch.setenv("REQUIRE_CAMPUS_VERIFICATION", "true")
    get_settings.cache_clear()
    try:
        with _client_for(db) as client:
            # Profile remains reachable so an unverified account is not locked out.
            assert client.get("/users/me", headers=auth_headers("a")).status_code == 200
            blocked = client.post(
                "/agent/chat",
                json={"message": "找周六下午羽毛球搭子"},
                headers=auth_headers("a"),
            )
            assert blocked.status_code == 403
            assert "campus identity" in blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_waiting_request_notification_is_private_and_markable(
    db, sample_users, auth_headers
):
    service = PartnerLoopService(db)
    waiting = service.record_request(
        "a",
        "waiting-session",
        {"activity": "飞盘", "availability": ["周五晚上"]},
        [],
    )
    service.record_request(
        "b",
        "later-session",
        {"activity": "飞盘", "availability": ["周六下午"]},
        ["a"],
    )
    assert waiting.status == "OPEN"

    try:
        with _client_for(db) as client:
            mine = client.get("/notifications", headers=auth_headers("a"))
            assert mine.status_code == 200
            assert len(mine.json()) == 1
            notification_id = mine.json()[0]["id"]

            hidden = client.post(
                f"/notifications/{notification_id}/read", headers=auth_headers("b")
            )
            assert hidden.status_code == 403
            read = client.post(
                f"/notifications/{notification_id}/read", headers=auth_headers("a")
            )
            assert read.status_code == 200
            assert read.json()["read_at"] is not None
    finally:
        app.dependency_overrides.clear()


def test_expired_partner_request_can_be_reopened(db, sample_users):
    expired = PartnerRequest(
        user_id="a",
        session_id="expired-demand",
        intent={"activity": "飞盘"},
        normalized_activity="飞盘",
        status="OPEN",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(expired)
    db.commit()
    service = PartnerLoopService(db)

    listed = service.list_requests("a")
    assert listed[0].status == "EXPIRED"
    reopened = service.set_request_status("a", expired.id, "OPEN")
    assert reopened.status == "OPEN"
    comparable_now = (
        datetime.now(timezone.utc)
        if reopened.expires_at.tzinfo
        else datetime.now()
    )
    assert reopened.expires_at > comparable_now + timedelta(days=13)


def test_availability_normalization_merges_common_chinese_variants():
    assert normalize_availability(
        ["星期五晚", "周五晚上", "本周六早上", "礼拜日下午"]
    ) == ["周五晚上", "周六上午", "周日下午"]


def test_notification_model_payload_does_not_require_sensitive_identity(db, sample_users):
    notice = Notification(
        user_id="a",
        kind="NEW_PARTNER_CANDIDATE",
        title="发现新的搭子候选",
        body="有同学也在寻找飞盘搭子。",
        payload={"activity": "飞盘"},
    )
    db.add(notice)
    db.commit()
    assert set(notice.payload) == {"activity"}


def test_report_category_is_a_closed_structured_set(db, sample_users, auth_headers):
    try:
        with _client_for(db) as client:
            invalid = client.post(
                "/report",
                json={
                    "reported_user_id": "b",
                    "category": "ARBITRARY_LABEL",
                    "reason": "内测类别校验",
                },
                headers=auth_headers("a"),
            )
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()
