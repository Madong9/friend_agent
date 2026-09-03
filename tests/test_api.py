from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import User
from backend.app.security import hash_password


def test_health_and_cloudbase_probe():
    with TestClient(app) as client:
        health = client.get("/health")
        cloudbase_probe = client.get("/__tcb_probe__")

        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert cloudbase_probe.status_code == 200
        assert cloudbase_probe.json() == health.json()


def test_api_endpoints(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get("/users/a").status_code == 401
            assert client.get("/users/a", headers=auth_headers("a")).status_code == 200
            assert client.get("/users/b", headers=auth_headers("a")).status_code == 403

            response = client.post(
                "/agent/recommend",
                json={
                    "message": "找周六下午羽毛球搭子，最好西区",
                    "limit": 2,
                },
                headers=auth_headers("a"),
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["matches"][0]["id"] == "b"
            trace = client.get(
                f"/agent/{result['session_id']}/trace", headers=auth_headers("a")
            )
            assert trace.status_code == 200
            assert len(trace.json()["entries"]) == 9
            assert (
                client.get(
                    f"/agent/{result['session_id']}/trace",
                    headers=auth_headers("b"),
                ).status_code
                == 403
            )

            spoofed_identity = client.post(
                "/agent/recommend",
                json={"user_id": "b", "message": "找搭子", "limit": 2},
                headers=auth_headers("a"),
            )
            assert spoofed_identity.status_code == 422

            assert (
                client.post(
                    "/feedback",
                    json={
                        "candidate_id": "b",
                        "feedback": "INTERESTED",
                    },
                    headers=auth_headers("a"),
                ).json()["matched"]
                is False
            )
            mutual = client.post(
                "/feedback",
                json={"candidate_id": "a", "feedback": "INTERESTED"},
                headers=auth_headers("b"),
            )
            assert mutual.json()["matched"] is True
            assert (
                client.get("/matches/a", headers=auth_headers("a")).json()[0][
                    "chat_enabled"
                ]
                is True
            )

            blocked = client.post(
                "/block",
                json={"blocked_user_id": "c"},
                headers=auth_headers("a"),
            )
            assert blocked.status_code == 201
            reported = client.post(
                "/report",
                json={
                    "reported_user_id": "c",
                    "reason": "发送贷款链接",
                },
                headers=auth_headers("a"),
            )
            assert reported.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_create_patch_and_natural_profile_api(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    payload = {
        "id": "new-user",
        "nickname": "新同学",
        "school_email": "new-user@ustc.edu.cn",
        "school": "中国科学技术大学",
        "campus": "西区",
        "grade": "大一",
        "major": "数学",
        "interests": [],
        "activities": [],
        "availability": [],
        "social_goals": [],
        "avoidances": [],
        "password": "NewUserPass123!",
    }
    try:
        with TestClient(app) as client:
            spoofed_verification = client.post(
                "/users",
                json={
                    **payload,
                    "id": "spoofed-verification",
                    "school_email": "spoofed-verification@ustc.edu.cn",
                    "verified": True,
                },
            )
            assert spoofed_verification.status_code == 422

            assert client.post("/users", json=payload).status_code == 201
            login = client.post(
                "/auth/login",
                json={
                    "school_email": "new-user@ustc.edu.cn",
                    "password": "NewUserPass123!",
                },
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            current_user = client.get("/auth/me", headers=headers).json()
            assert current_user["id"] == "new-user"
            assert "verified" not in current_user
            assert client.post("/auth/logout", headers=headers).status_code == 200
            assert client.get("/auth/me", headers=headers).status_code == 401
            fresh_login = client.post(
                "/auth/login",
                json={
                    "school_email": "new-user@ustc.edu.cn",
                    "password": "NewUserPass123!",
                },
            )
            assert fresh_login.status_code == 200
            fresh_headers = {
                "Authorization": f"Bearer {fresh_login.json()['access_token']}"
            }
            assert (
                client.post(
                    "/auth/login",
                    json={
                        "school_email": "new-user@ustc.edu.cn",
                        "password": "wrong-password",
                    },
                ).status_code
                == 401
            )
            assert (
                client.patch(
                    "/users/new-user", json={"bio": "你好"}, headers=fresh_headers
                ).json()["bio"]
                == "你好"
            )
            parsed = client.post(
                "/users/new-user/profile/parse",
                json={"text": "我大一，喜欢摄影和跑步，比较慢热，晚上有空。"},
                headers=fresh_headers,
            )
            assert parsed.status_code == 200
            assert client.get("/users/new-user", headers=fresh_headers).json()[
                "interests"
            ] == ["跑步", "摄影"]

            invalid_domain = {
                **payload,
                "id": "untrusted-user",
                "school_email": "untrusted-user@personal.com",
            }
            rejected = client.post("/users", json=invalid_domain)
            assert rejected.status_code == 403

            empty_nickname = client.patch(
                "/users/new-user", json={"nickname": "   "}, headers=fresh_headers
            )
            assert empty_nickname.status_code == 422

            db.add(
                User(
                    id="unverified-user",
                    nickname="未认证用户",
                    school_email="unverified-user@ustc.edu.cn",
                    school="中国科学技术大学",
                    campus="西区",
                    grade="大一",
                    major="数学",
                    password_hash=hash_password("UnverifiedPass123!"),
                    verified=False,
                )
            )
            db.commit()
            unverified_login = client.post(
                "/auth/login",
                json={
                    "school_email": "unverified-user@ustc.edu.cn",
                    "password": "UnverifiedPass123!",
                },
            )
            assert unverified_login.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_ustc_cas_login_flow_creates_local_jwt(db, monkeypatch):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    class FakeResponse:
        text = """
        <cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
          <cas:authenticationSuccess>
            <cas:user>ustc-a</cas:user>
            <cas:attributes>
              <cas:mail>a@ustc.edu.cn</cas:mail>
              <cas:uid>ustc-a</cas:uid>
              <cas:displayName>甲</cas:displayName>
            </cas:attributes>
          </cas:authenticationSuccess>
        </cas:serviceResponse>
        """

        def raise_for_status(self):
            return None

    def fake_get(url, params=None, timeout=None):
        assert "serviceValidate" in url
        assert params is not None
        return FakeResponse()

    monkeypatch.setattr("backend.app.api.auth.httpx.get", fake_get)

    try:
        with TestClient(app) as client:
            login = client.get("/auth/ustc/login?next=/matches", follow_redirects=False)
            assert login.status_code == 302
            login_query = parse_qs(urlparse(login.headers["location"]).query)
            assert login_query["service"][0].endswith("/auth/ustc/callback")

            callback = client.get(
                "/auth/ustc/callback",
                params={"ticket": "ST-123", "state": login_query["state"][0]},
                follow_redirects=False,
            )
            assert callback.status_code == 302
            redirected = urlparse(callback.headers["location"])
            token = parse_qs(redirected.fragment)["access_token"][0]
            me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            body = me.json()
            assert body["school"] == "中国科学技术大学"
            assert body["nickname"] == "甲"
    finally:
        app.dependency_overrides.clear()


def test_ustc_cas_login_failure_redirects_to_frontend(db, monkeypatch):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    def fake_get(url, params=None, timeout=None):
        class FakeResponse:
            text = """
            <cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">
              <cas:authenticationFailure>ticket invalid</cas:authenticationFailure>
            </cas:serviceResponse>
            """

            def raise_for_status(self):
                return None

        return FakeResponse()

    monkeypatch.setattr("backend.app.api.auth.httpx.get", fake_get)

    try:
        with TestClient(app) as client:
            login = client.get("/auth/ustc/login?next=/matches", follow_redirects=False)
            login_query = parse_qs(urlparse(login.headers["location"]).query)
            callback = client.get(
                "/auth/ustc/callback",
                params={"ticket": "ST-123", "state": login_query["state"][0]},
                follow_redirects=False,
            )
            assert callback.status_code == 302
            redirected = urlparse(callback.headers["location"])
            query = parse_qs(redirected.query)
            assert query["auth_stage"][0] == "ustc"
            assert "ticket invalid" in query["auth_error"][0]
    finally:
        app.dependency_overrides.clear()
