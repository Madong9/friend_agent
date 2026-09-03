from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import and_, desc, func, or_, select

from backend.app.models import Block, Interaction, Message, User
from backend.app.repositories.cloudbase_http import (
    CloudBaseDataError,
    CloudBaseHttpSession,
)


def user_row(user_id: str = "user001", nickname: str = "小宇") -> dict:
    return {
        "id": user_id,
        "nickname": nickname,
        "school_email": f"{user_id}@ustc.edu.cn",
        "wechat_openid": None,
        "school_uid": None,
        "school_display_name": None,
        "identity_provider": "email",
        "school": "中国科学技术大学",
        "campus": "西区",
        "grade": "研一",
        "major": "计算机",
        "bio": "",
        "social_goals": ["学习搭子"],
        "interests": ["编程"],
        "activities": ["自习"],
        "availability": ["周六下午"],
        "social_style": "随和",
        "avoidances": [],
        "recommendation_enabled": True,
        "verified": True,
        "password_hash": None,
        "token_version": 0,
        "last_token_revoked_at": None,
        "is_mock": True,
        "created_at": "2026-08-28T10:00:00+00:00",
        "updated_at": None,
    }


def make_session(handler) -> CloudBaseHttpSession:
    return CloudBaseHttpSession(
        env_id="campus-social-test",
        api_key="server-secret",
        transport=httpx.MockTransport(handler),
    )


def test_select_translates_filters_order_limit_and_hydrates_model():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=[user_row()])

    with make_session(handler) as db:
        rows = list(
            db.scalars(
                select(User)
                .where(User.id != "other", User.is_mock.is_(True))
                .order_by(desc(User.created_at))
                .limit(3)
            )
        )
    assert rows[0].nickname == "小宇"
    assert rows[0].created_at == datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
    request = captured["request"]
    assert request.url.path.endswith("/v1/rdb/rest/users")
    assert request.headers["authorization"] == "Bearer server-secret"
    assert request.url.params["id"] == "neq.other"
    assert request.url.params["is_mock"] == "is.true"
    assert request.url.params["order"] == "created_at.desc"
    assert request.url.params["limit"] == "3"


def test_hydration_accepts_cloudbase_five_digit_fractional_seconds():
    row = user_row()
    row["created_at"] = "2026-08-31T23:51:35.90409+08:00"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[row])

    with make_session(handler) as db:
        user = db.get(User, "user001")

    assert user is not None
    assert user.created_at == datetime(
        2026,
        8,
        31,
        23,
        51,
        35,
        904090,
        tzinfo=timezone(timedelta(hours=8)),
    )


def test_or_filter_and_scalar_column_use_postgrest_contract():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=[{"id": 9}])

    with make_session(handler) as db:
        block_id = db.scalar(
            select(Block.id).where(
                or_(
                    and_(Block.blocker_id == "a", Block.blocked_id == "b"),
                    and_(Block.blocker_id == "b", Block.blocked_id == "a"),
                )
            )
        )
    assert block_id == 9
    query = captured["request"].url.params
    assert query["select"] == "id"
    assert query["or"].startswith("(and(")
    assert "blocker_id.eq.a" in query["or"]


def test_insert_and_dirty_update_use_rest_crud_with_server_key():
    calls: list[tuple[str, str, dict | list]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        calls.append((request.method, request.url.path, body))
        if request.method == "POST":
            return httpx.Response(201, json=[body])
        if request.method == "PATCH":
            return httpx.Response(200, json=[body])
        raise AssertionError(request.method)

    user = User(
        id="new-user",
        nickname="新同学",
        school_email="new-user@ustc.edu.cn",
        school="中国科学技术大学",
        campus="西区",
        grade="研一",
        major="计算机",
        verified=True,
    )
    with make_session(handler) as db:
        db.add(user)
        db.commit()
        user.nickname = "改名后"
        db.commit()
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("/users")
    assert calls[0][2]["social_goals"] == []
    assert calls[0][2]["recommendation_enabled"] is True
    assert calls[1][0] == "PATCH"
    assert calls[1][2]["nickname"] == "改名后"


def test_rpc_uses_postgrest_rpc_path_and_json_parameters():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json={"status": "recorded", "match_id": None})

    with make_session(handler) as db:
        result = db.rpc(
            "campus_record_feedback",
            {"p_user_id": "a", "p_candidate_id": "b", "p_feedback": "LIKE"},
        )
    assert result == {"status": "recorded", "match_id": None}
    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path.endswith("/rpc/campus_record_feedback")
    assert json.loads(request.content)["p_feedback"] == "LIKE"


def test_in_filter_is_encoded_for_postgrest():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=[])

    with make_session(handler) as db:
        list(
            db.scalars(
                select(Interaction).where(Interaction.kind.in_(["PASS", "LIKE"]))
            )
        )
    assert captured["request"].url.params["kind"] == 'in.("PASS","LIKE")'


def test_count_uses_postgrest_exact_content_range():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, headers={"Content-Range": "0-0/12"})

    with make_session(handler) as db:
        result = db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.recipient_id == "user001", Message.read_at.is_(None))
        )
    assert result == 12
    request = captured["request"]
    assert request.method == "HEAD"
    assert request.headers["prefer"] == "count=exact"
    assert request.url.params["read_at"] == "is.null"


def test_http_error_is_sanitized_and_never_contains_server_key():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "permission denied", "internal": "do-not-leak"},
        )

    with make_session(handler) as db:
        try:
            db.healthcheck()
        except CloudBaseDataError as exc:
            message = str(exc)
        else:
            raise AssertionError("403 must be surfaced as CloudBaseDataError")
    assert "permission denied" in message
    assert "server-secret" not in message
    assert "do-not-leak" not in message


def test_in_place_json_change_is_detected_by_unit_of_work():
    patches = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[user_row()])
        if request.method == "PATCH":
            body = json.loads(request.content)
            patches.append(body)
            return httpx.Response(200, json=[body])
        raise AssertionError(request.method)

    with make_session(handler) as db:
        user = db.get(User, "user001")
        user.interests.append("阅读")
        db.commit()
    assert patches[0]["interests"] == ["编程", "阅读"]
