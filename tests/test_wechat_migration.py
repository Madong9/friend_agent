"""WeChat identity login flow and anti-impersonation guarantees."""

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.main import app
from backend.app.services.wechat_identity import WechatIdentity, WechatIdentityService


def test_client_cannot_impersonate_arbitrary_user(db, sample_users, auth_headers):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get("/users/b", headers=auth_headers("a")).status_code == 403
            assert (
                client.patch(
                    "/users/b", json={"bio": "hax"}, headers=auth_headers("a")
                ).status_code
                == 403
            )
            me = client.get("/users/me", headers=auth_headers("a")).json()
            assert me["id"] == "a"
            spoofed = client.post(
                "/feedback",
                json={"candidate_id": "c", "feedback": "LIKE", "user_id": "b"},
                headers=auth_headers("a"),
            )
            assert spoofed.status_code == 422
            agent_spoof = client.post(
                "/agent/chat",
                json={"message": "找搭子", "user_id": "b"},
                headers=auth_headers("a"),
            )
            assert agent_spoof.status_code == 422
            server_owned_match = client.post(
                "/feedback",
                json={"candidate_id": "b", "feedback": "MATCHED"},
                headers=auth_headers("a"),
            )
            assert server_owned_match.status_code == 422
            safety_action = client.post(
                "/feedback",
                json={"candidate_id": "b", "feedback": "BLOCK"},
                headers=auth_headers("a"),
            )
            assert safety_action.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_wechat_login_creates_and_reuses_stub_user(db, monkeypatch):
    def override_db():
        yield db

    async def fake_code_to_openid(self, code: str):
        return WechatIdentity(openid=f"openid-{code}")

    monkeypatch.setattr(WechatIdentityService, "code_to_openid", fake_code_to_openid)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            first = client.post("/auth/wechat", json={"code": "code-1"})
            assert first.status_code == 200, first.text
            user = first.json()["user"]
            assert user["id"].startswith("wx-")
            assert user["is_mock"] is False

            second = client.post("/auth/wechat", json={"code": "code-1"})
            assert second.status_code == 200
            assert second.json()["user"]["id"] == user["id"]

            me = client.get(
                "/users/me",
                headers={"Authorization": f"Bearer {first.json()['access_token']}"},
            )
            assert me.status_code == 200
            assert me.json()["id"] == user["id"]
    finally:
        app.dependency_overrides.clear()


def test_wechat_login_rejects_unconfigured_backend(db, monkeypatch):
    from backend.app.services.wechat_identity import WechatIdentityError

    def override_db():
        yield db

    async def failing_code_to_openid(self, code: str):
        raise WechatIdentityError("WECHAT_APP_ID is not configured")

    monkeypatch.setattr(WechatIdentityService, "code_to_openid", failing_code_to_openid)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post("/auth/wechat", json={"code": "code-1"})
            assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wechat_identity_requires_both_backend_credentials(db, monkeypatch):
    from backend.app.services.wechat_identity import WechatIdentityError

    monkeypatch.setenv("WECHAT_APP_ID", "configured-app-id")
    monkeypatch.delenv("WECHAT_APP_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(WechatIdentityError, match="credentials are not configured"):
            await WechatIdentityService(db).code_to_openid("temporary-code")
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_wechat_identity_wraps_transport_failures(db, monkeypatch):
    from backend.app.services.wechat_identity import WechatIdentityError

    async def timeout(*_args, **_kwargs):
        raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setenv("WECHAT_APP_ID", "configured-app-id")
    monkeypatch.setenv("WECHAT_APP_SECRET", "configured-secret")
    monkeypatch.setattr(httpx.AsyncClient, "get", timeout)
    get_settings.cache_clear()
    try:
        with pytest.raises(WechatIdentityError, match="temporarily unavailable"):
            await WechatIdentityService(db).code_to_openid("temporary-code")
    finally:
        get_settings.cache_clear()
