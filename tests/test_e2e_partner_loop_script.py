from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.app.models import (
    Interaction,
    Match,
    Message,
    Notification,
    PartnerRequest,
    User,
)
from backend.app.services.partner_loop import PartnerLoopService
from scripts.e2e_partner_loop import (
    ACTIVITY,
    AVAILABILITY,
    CAMPUS,
    E2E_IDENTITY_PROVIDER,
    E2EStageError,
    _print_stage_error,
    cleanup_e2e,
    dry_run_e2e,
    execute_e2e,
)


def _real_requester(db) -> User:
    user = User(
        id="real-a",
        nickname="真实A",
        wechat_openid="test-only-openid-a",
        identity_provider="wechat",
        school="中国科学技术大学",
        campus=CAMPUS,
        grade="研一",
        major="计算机",
        bio="测试画像",
        social_goals=["运动搭子"],
        interests=[ACTIVITY],
        activities=[ACTIVITY],
        availability=[AVAILABILITY],
        social_style="随和",
        avoidances=[],
        recommendation_enabled=True,
        verified=True,
        campus_verified=True,
        is_mock=False,
    )
    db.add(user)
    db.commit()
    return user


def test_real_a_synthetic_b_uses_production_partner_loop_and_cleans_exact_scope(
    db, tmp_path
):
    requester = _real_requester(db)
    original_profile = {
        "nickname": requester.nickname,
        "activities": deepcopy(requester.activities),
        "availability": deepcopy(requester.availability),
        "wechat_openid": requester.wechat_openid,
    }
    request = PartnerLoopService(db).record_request(
        requester.id,
        "real-a-open-request",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": CAMPUS,
            "hard_constraints": ["campus"],
        },
        [],
    )
    manifest = tmp_path / "partner-loop.json"

    summary = execute_e2e(db, request_id=request.id, manifest_path=manifest)

    assert summary.request_found is True
    assert summary.candidate_created is True
    assert summary.match_eligible is True
    assert summary.notification_created is True
    assert summary.notification_recipient_is_a is True
    assert manifest.exists()

    candidate = db.scalar(
        select(User).where(User.identity_provider == E2E_IDENTITY_PROVIDER)
    )
    assert candidate is not None
    assert candidate.nickname.startswith("[E2E临时]")
    assert candidate.campus == CAMPUS
    assert candidate.activities == [ACTIVITY]
    assert candidate.availability == [AVAILABILITY]
    assert candidate.is_mock is False
    assert candidate.wechat_openid is None

    notices = list(db.scalars(select(Notification)))
    assert len(notices) == 1
    assert notices[0].user_id == requester.id
    assert notices[0].payload["request_id"] == request.id

    # Simulate B-related rows that might be generated during phone verification;
    # cleanup must remove these while preserving A and A's original OPEN request.
    db.add_all(
        [
            Interaction(
                actor_id=requester.id,
                target_id=candidate.id,
                kind="LIKE",
                payload={},
            ),
            Match(
                user_a_id=min(requester.id, candidate.id),
                user_b_id=max(requester.id, candidate.id),
                status="MATCHED",
            ),
            Message(
                sender_id=requester.id,
                recipient_id=candidate.id,
                body="test-only",
                safety_result={},
            ),
        ]
    )
    db.commit()

    cleanup = cleanup_e2e(db, manifest_path=manifest)

    assert cleanup == {
        "candidate_removed": True,
        "notification_removed": True,
        "manifest_removed": True,
    }
    assert db.get(User, candidate.id) is None
    assert list(db.scalars(select(Notification))) == []
    assert list(db.scalars(select(Interaction))) == []
    assert list(db.scalars(select(Match))) == []
    assert list(db.scalars(select(Message))) == []
    preserved = db.get(User, requester.id)
    assert preserved is not None
    assert {
        "nickname": preserved.nickname,
        "activities": preserved.activities,
        "availability": preserved.availability,
        "wechat_openid": preserved.wechat_openid,
    } == original_profile
    assert db.get(type(request), request.id).status == "OPEN"


def test_e2e_candidate_must_pass_existing_hard_filters(db, tmp_path):
    requester = _real_requester(db)
    request = PartnerLoopService(db).record_request(
        requester.id,
        "wrong-campus-open-request",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": "西区",
            "hard_constraints": ["campus"],
        },
        [],
    )

    from scripts.e2e_partner_loop import E2EValidationError

    try:
        execute_e2e(
            db,
            request_id=request.id,
            manifest_path=tmp_path / "partner-loop.json",
        )
    except E2EValidationError as exc:
        assert "production matching rules" in str(exc)
    else:
        raise AssertionError("mismatched campus must not create an E2E notification")

    assert list(db.scalars(select(Notification))) == []
    assert list(
        db.scalars(select(User).where(User.identity_provider == E2E_IDENTITY_PROVIDER))
    ) == []
    assert not (tmp_path / "partner-loop.json").exists()


@pytest.mark.parametrize(
    "request_availability",
    [
        ["下午"],
        ["周六", "下午"],
    ],
)
def test_e2e_candidate_mirrors_split_agent_availability_tokens(
    db, tmp_path, request_availability
):
    requester = _real_requester(db)
    request = PartnerLoopService(db).record_request(
        requester.id,
        "split-availability-open-request",
        {
            "activity": ACTIVITY,
            "availability": request_availability,
            "campus": CAMPUS,
            "hard_constraints": ["campus"],
        },
        [],
    )
    manifest = tmp_path / "partner-loop.json"

    summary = execute_e2e(db, request_id=request.id, manifest_path=manifest)

    assert summary.match_eligible is True
    assert summary.notification_created is True
    candidate = db.scalar(
        select(User).where(User.identity_provider == E2E_IDENTITY_PROVIDER)
    )
    assert candidate is not None
    assert AVAILABILITY in candidate.availability
    assert set(request_availability).issubset(set(candidate.availability))


def test_dry_run_selects_unique_request_without_database_changes(
    db, tmp_path, monkeypatch, capsys
):
    requester = _real_requester(db)
    request = PartnerLoopService(db).record_request(
        requester.id,
        "dry-run-open-request",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": CAMPUS,
            "hard_constraints": ["campus"],
        },
        [],
    )
    manifest = tmp_path / "partner-loop.json"

    def forbidden_commit():
        raise AssertionError("dry-run must not call commit")

    monkeypatch.setattr(db, "commit", forbidden_commit)
    result = dry_run_e2e(db, request_id=None, manifest_path=manifest)
    output = capsys.readouterr().out

    assert result == 0
    assert "A request found: yes" in output
    assert f"request id: {request.id}" in output
    assert "activity: 飞盘" in output
    assert "campus: 高新区" in output
    assert "availability: 周六下午" in output
    assert "status: OPEN" in output
    assert "request valid: yes" in output
    assert "B would be created: yes" in output
    assert "database changes made: no" in output
    assert requester.id not in output
    assert requester.nickname not in output
    assert requester.wechat_openid not in output
    assert not manifest.exists()
    assert list(db.scalars(select(Notification))) == []
    assert list(
        db.scalars(select(User).where(User.identity_provider == E2E_IDENTITY_PROVIDER))
    ) == []


def test_dry_run_reads_production_partner_request_schema(db, tmp_path, monkeypatch, capsys):
    requester = _real_requester(db)
    now = datetime.now(timezone.utc)
    db.add(
        PartnerRequest(
            id=5,
            user_id=requester.id,
            session_id="production-schema-session",
            intent={
                "goal": "find_partner",
                "activity": "飞盘",
                "availability": ["Saturday afternoon"],
                "campus": "高新区",
            },
            normalized_activity="飞盘",
            status="OPEN",
            note="",
            expires_at=now + timedelta(days=7),
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()

    def forbidden_commit():
        raise AssertionError("dry-run must not call commit")

    monkeypatch.setattr(db, "commit", forbidden_commit)
    result = dry_run_e2e(
        db, request_id=None, manifest_path=tmp_path / "partner-loop.json"
    )
    output = capsys.readouterr().out

    assert result == 0
    assert output == (
        "A request found: yes\n"
        "request id: 5\n"
        "activity: 飞盘\n"
        "campus: 高新区\n"
        "availability: Saturday afternoon\n"
        "status: OPEN\n"
        "request valid: yes\n"
        "B would be created: yes\n"
        "database changes made: no\n"
    )
    assert requester.id not in output
    assert requester.wechat_openid not in output
    assert list(db.scalars(select(Notification))) == []


def test_dry_run_reports_no_request_without_changes(db, tmp_path, capsys):
    result = dry_run_e2e(
        db, request_id=None, manifest_path=tmp_path / "partner-loop.json"
    )

    assert result == 2
    assert capsys.readouterr().out == (
        "A request found: no\n"
        "database changes made: no\n"
    )


def test_dry_run_lists_safe_request_ids_and_supports_selection(
    db, tmp_path, monkeypatch, capsys
):
    requester = _real_requester(db)
    service = PartnerLoopService(db)
    first = service.record_request(
        requester.id,
        "dry-run-multiple-one",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": CAMPUS,
            "hard_constraints": ["campus"],
        },
        [],
    )
    second = service.record_request(
        requester.id,
        "dry-run-multiple-two",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": CAMPUS,
            "hard_constraints": ["campus"],
        },
        [],
    )
    manifest = tmp_path / "partner-loop.json"

    multiple_result = dry_run_e2e(db, request_id=None, manifest_path=manifest)
    multiple_output = capsys.readouterr().out
    assert multiple_result == 2
    assert "A request found: multiple" in multiple_output
    assert f"request id: {first.id}" in multiple_output
    assert f"request id: {second.id}" in multiple_output
    assert "activity: 飞盘" in multiple_output
    assert "campus: 高新区" in multiple_output
    assert "availability: 周六下午" in multiple_output
    assert "created_at:" in multiple_output
    assert (
        "./.venv/bin/python scripts/e2e_partner_loop.py --request-id ID"
        in multiple_output
    )
    assert requester.id not in multiple_output
    assert requester.nickname not in multiple_output
    assert requester.wechat_openid not in multiple_output

    def forbidden_commit():
        raise AssertionError("dry-run must not call commit")

    monkeypatch.setattr(db, "commit", forbidden_commit)
    selected_result = dry_run_e2e(
        db, request_id=second.id, manifest_path=manifest
    )
    selected_output = capsys.readouterr().out
    assert selected_result == 0
    assert f"request id: {second.id}" in selected_output
    assert f"request id: {first.id}" not in selected_output
    assert "request valid: yes" in selected_output
    assert "database changes made: no" in selected_output


def test_dry_run_reports_safe_matching_value_error_stage(
    db, tmp_path, monkeypatch, capsys
):
    requester = _real_requester(db)
    request = PartnerLoopService(db).record_request(
        requester.id,
        "matching-value-error",
        {
            "activity": ACTIVITY,
            "availability": [AVAILABILITY],
            "campus": CAMPUS,
        },
        [],
    )

    def fail_matching(*_args, **_kwargs):
        raise ValueError("invalid matching input format")

    monkeypatch.setattr(
        "scripts.e2e_partner_loop._verify_production_matching", fail_matching
    )
    with pytest.raises(E2EStageError) as raised:
        dry_run_e2e(
            db,
            request_id=request.id,
            manifest_path=tmp_path / "partner-loop.json",
        )

    error = raised.value
    assert error.stage == "matching"
    assert error.exception_type == "ValueError"
    assert error.safe_message == "invalid matching input format"
    _print_stage_error(error)
    output = capsys.readouterr().out
    assert "stage: matching" in output
    assert "exception type: ValueError" in output
    assert "exception message: invalid matching input format" in output
    assert requester.id not in output
    assert requester.wechat_openid not in output


def test_stage_error_withholds_sensitive_exception_message(capsys):
    error = E2EStageError(
        "create_notification", ValueError("token=do-not-print user_id=private")
    )

    _print_stage_error(error)

    output = capsys.readouterr().out
    assert "stage: create_notification" in output
    assert "exception type: ValueError" in output
    assert "message withheld by sensitive-data filter" in output
    assert "do-not-print" not in output
    assert "private" not in output
