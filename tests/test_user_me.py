"""/users/me and /matches/me: identity decided by the backend, never the client."""

from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.llm.mock import MockLLMProvider
from backend.app.main import app
from backend.app.services import SocialService


def test_user_me(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            me = client.get("/users/me", headers=auth_headers("a"))
            assert me.status_code == 200
            assert me.json()["id"] == "a"
            changed_school = client.patch(
                "/users/me",
                json={"school": "中国科学技术大学（内测自填）"},
                headers=auth_headers("a"),
            )
            assert changed_school.status_code == 200
            assert changed_school.json()["school"].endswith("（内测自填）")
            updated = client.patch(
                "/users/me",
                json={"bio": "你好，世界"},
                headers=auth_headers("a"),
            )
            assert updated.status_code == 200
            assert updated.json()["bio"] == "你好，世界"
            assert client.get("/users/me").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_my_profile_parse_endpoint(db, sample_users, auth_headers, monkeypatch):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(
        "backend.app.api.users.create_llm_provider", lambda: MockLLMProvider()
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/me/profile/parse",
                json={"text": "我研一，喜欢跑步和摄影，比较慢热，晚上有空。"},
                headers=auth_headers("a"),
            )
            assert response.status_code == 200
            me = client.get("/users/me", headers=auth_headers("a"))
            assert me.json()["interests"] == ["跑步", "摄影"]
            assert me.json()["grade"] == "研一"
    finally:
        app.dependency_overrides.clear()


def test_matches_me_lists_only_own_matches(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get("/matches/me", headers=auth_headers("a")).json() == []
            service = SocialService(db)
            service.record_feedback("a", "b", "LIKE")
            service.record_feedback("b", "a", "LIKE")
            mine = client.get("/matches/me", headers=auth_headers("a")).json()
            assert len(mine) == 1
            assert mine[0]["partner"]["id"] == "b"

            match_id = mine[0]["match_id"]
            detail = client.get(
                f"/matches/me/{match_id}", headers=auth_headers("a")
            ).json()
            assert detail["partner"]["id"] == "b"

            other = client.get("/matches/me", headers=auth_headers("c")).json()
            assert other == []
            forbidden = client.get(f"/matches/me/{match_id}", headers=auth_headers("c"))
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
