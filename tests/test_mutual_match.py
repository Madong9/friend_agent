"""Mutual match rules: double opt-in, demo matches never open contact."""

import pytest
from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import User
from backend.app.services import SocialService
from backend.app.services.conversation import ConversationService
from tests.conftest import TEST_PASSWORD_HASH


def test_mutual_like_creates_match(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = client.post(
                "/feedback",
                json={"candidate_id": "b", "feedback": "LIKE"},
                headers=auth_headers("a"),
            )
            assert first.json()["matched"] is False
            second = client.post(
                "/feedback",
                json={"candidate_id": "a", "feedback": "LIKE"},
                headers=auth_headers("b"),
            )
            assert second.json()["matched"] is True
            matches = client.get("/matches/me", headers=auth_headers("a")).json()
            assert matches[0]["partner"]["id"] == "b"
            assert matches[0]["demo_match"] is False
            assert matches[0]["chat_enabled"] is True
    finally:
        app.dependency_overrides.clear()


def test_single_like_does_not_create_match(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/feedback",
                json={"candidate_id": "b", "feedback": "LIKE"},
                headers=auth_headers("a"),
            )
            assert response.json()["matched"] is False
            assert client.get("/matches/me", headers=auth_headers("a")).json() == []
    finally:
        app.dependency_overrides.clear()


def test_demo_match_between_mock_users_does_not_open_contact(db, auth_headers):
    def override_db():
        yield db

    for user_id, nickname in (("mock-a", "模拟甲"), ("mock-b", "模拟乙")):
        db.add(
            User(
                id=user_id,
                nickname=nickname,
                school="中国科学技术大学",
                campus="西区",
                grade="研一",
                major="计算机",
                interests=["羽毛球"],
                availability=["周六下午"],
                social_goals=["运动搭子"],
                password_hash=TEST_PASSWORD_HASH,
                verified=True,
                is_mock=True,
            )
        )
    db.commit()
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.post(
                "/feedback",
                json={"candidate_id": "mock-b", "feedback": "LIKE"},
                headers=auth_headers("mock-a"),
            )
            mutual = client.post(
                "/feedback",
                json={"candidate_id": "mock-a", "feedback": "LIKE"},
                headers=auth_headers("mock-b"),
            )
            body = mutual.json()
            assert body["matched"] is True
            assert body["demo_match"] is True
            assert body["chat_enabled"] is False

            matches = client.get("/matches/me", headers=auth_headers("mock-a")).json()
            assert matches[0]["demo_match"] is True
            assert matches[0]["chat_enabled"] is False

            with pytest.raises(PermissionError):
                ConversationService(db).require_active_match("mock-a", "mock-b")
    finally:
        app.dependency_overrides.clear()


def test_agent_response_exposes_score_fields_before_match(
    db, sample_users, auth_headers
):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            result = client.post(
                "/agent/recommend",
                json={"message": "找周六下午羽毛球搭子，最好西区", "limit": 2},
                headers=auth_headers("a"),
            ).json()
            top = result["matches"][0]
            assert top["id"] == "b"
            assert top["display_name"] == top["nickname"]
            assert top["score"] == top["total"]
            assert top["score_breakdown"] == top["features"]
            assert top["match_status"] == "none"
            assert isinstance(top["is_mock"], bool)
    finally:
        app.dependency_overrides.clear()


def test_agent_response_marks_existing_mutual_match(db, sample_users, auth_headers):
    def override_db():
        yield db

    SocialService(db).record_feedback("a", "b", "LIKE")
    SocialService(db).record_feedback("b", "a", "LIKE")
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            result = client.post(
                "/agent/recommend",
                json={"message": "找周六下午羽毛球搭子", "limit": 5},
                headers=auth_headers("a"),
            ).json()
            matched = next(item for item in result["matches"] if item["id"] == "b")
            assert matched["match_status"] == "matched"
    finally:
        app.dependency_overrides.clear()
