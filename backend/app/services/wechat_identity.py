"""WeChat identity mapping to internal users.

The first version deliberately avoids phone/real-name/unionid flows. The backend
exchanges a WeChat login code for an openid via jscode2session, then maps that openid
to an internal user (creating a stub profile on first login). Clients never send a
raw internal user id for identity: the backend decides it from the trusted context.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User


@dataclass(frozen=True)
class WechatIdentity:
    openid: str
    session_key: str | None = None
    unionid: str | None = None


class WechatIdentityError(ValueError):
    pass


class WechatIdentityService:
    """Exchange trusted login code for openid and map to internal user id."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    async def code_to_openid(self, code: str) -> WechatIdentity:
        if not code:
            raise WechatIdentityError("missing WeChat login code")
        params = {
            "appid": self.settings.wechat_app_id,
            "secret": self.settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatIdentityError(
                "WeChat backend credentials are not configured; "
                "use DEV_AUTH_MODE for local testing"
            )
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                trust_env=self.settings.outbound_http_trust_env,
            ) as client:
                response = await client.get(
                    self.settings.wechat_code2session_url, params=params
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise WechatIdentityError(
                "WeChat identity service is temporarily unavailable"
            ) from exc
        errcode = data.get("errcode")
        if errcode:
            raise WechatIdentityError(
                f"WeChat rejected the login code (error {errcode})"
            )
        openid = data.get("openid")
        if not openid:
            raise WechatIdentityError("wechat response did not include openid")
        return WechatIdentity(
            openid=openid,
            session_key=data.get("session_key"),
            unionid=data.get("unionid"),
        )

    def resolve_or_create_user(self, openid: str, nickname: str | None = None) -> User:
        user = self.db.query(User).filter(User.wechat_openid == openid).one_or_none()
        if user is not None:
            return user
        user_id = f"wx-{uuid4().hex[:12]}"
        while self.db.get(User, user_id) is not None:
            user_id = f"wx-{uuid4().hex[:12]}"
        user = User(
            id=user_id,
            nickname=(nickname or "同学").strip() or "同学",
            wechat_openid=openid,
            identity_provider="wechat",
            school="待验证",
            campus="待完善",
            grade="待完善",
            major="待完善",
            social_goals=[],
            interests=[],
            activities=[],
            availability=[],
            recommendation_enabled=True,
            verified=True,
            campus_verified=False,
            is_mock=False,
        )
        self.db.add(user)
        return user
