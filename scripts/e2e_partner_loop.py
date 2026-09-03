#!/usr/bin/env python3
"""Run the private A(real) + B(synthetic) partner-loop E2E scenario.

This script is intentionally local-only: it imports the production matching and
partner-loop services directly and never exposes an HTTP test endpoint.  The
default command is non-mutating; ``--execute`` is required to create the marked
temporary user and ``--cleanup`` is required to remove its exact test scope.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, or_, select


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import get_settings  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.matching.engine import MatchingEngine  # noqa: E402
from backend.app.matching.similarity import normalize_tag  # noqa: E402
from backend.app.models import (  # noqa: E402
    AgentSessionRecord,
    AgentTraceRecord,
    Block,
    Interaction,
    Match,
    Message,
    Notification,
    PartnerRequest,
    Preference,
    Report,
    User,
)
from backend.app.services.partner_loop import PartnerLoopService  # noqa: E402


ACTIVITY = "飞盘"
AVAILABILITY = "周六下午"
CAMPUS = "高新区"
E2E_USER_PREFIX = "e2e-frisbee-b-"
E2E_SESSION_PREFIX = "e2e-frisbee-session-"
E2E_NICKNAME = "[E2E临时]飞盘搭子B"
E2E_IDENTITY_PROVIDER = "e2e_local"
E2E_EMAIL_DOMAIN = "e2e.invalid"
NOTICE_KIND = "NEW_PARTNER_CANDIDATE"
DEFAULT_MANIFEST = ROOT / ".e2e" / "partner-loop.json"


class E2EValidationError(RuntimeError):
    """Expected, privacy-safe precondition failure."""


class E2EStageError(RuntimeError):
    """Unexpected failure annotated with a safe E2E lifecycle stage."""

    def __init__(self, stage: str, cause: Exception):
        super().__init__(stage)
        self.stage = stage
        self.exception_type = type(cause).__name__
        self.safe_message = _safe_exception_message(cause)


@dataclass
class E2ESummary:
    request_found: bool = False
    candidate_created: bool = False
    match_eligible: bool = False
    notification_created: bool = False
    notification_recipient_is_a: bool = False


@dataclass(frozen=True)
class CleanupManifest:
    version: int
    run_id: str
    b_user_id: str
    b_session_id: str
    notification_ids: list[int]
    created_at: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_exception_message(error: Exception) -> str:
    message = " ".join(str(error).split())[:300]
    if not message:
        return "no message"
    lowered = message.casefold()
    sensitive_terms = (
        "user_id",
        "openid",
        "jwt",
        "secret",
        "authorization",
        "bearer",
        "api_key",
        "apikey",
        "token",
    )
    if any(term in lowered for term in sensitive_terms):
        return "message withheld by sensitive-data filter"
    if re.search(r"[\w.+-]+@[\w.-]+", message):
        return "message withheld by sensitive-data filter"
    if re.search(r"\beyJ[\w-]*\.[\w.-]+", message):
        return "message withheld by sensitive-data filter"
    return message


def _stage_call(stage: str, operation):
    try:
        return operation()
    except (E2EValidationError, E2EStageError):
        raise
    except Exception as exc:
        raise E2EStageError(stage, exc) from exc


def _print_stage_error(error: E2EStageError) -> None:
    print("E2E failed safely")
    print(f"stage: {error.stage}")
    print(f"exception type: {error.exception_type}")
    print(f"exception message: {error.safe_message}")


def _write_manifest(path: Path, manifest: CleanupManifest, *, replace: bool) -> None:
    if path.exists() and not replace:
        raise E2EValidationError(
            "cleanup manifest already exists; run --cleanup before another E2E run"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _load_manifest(path: Path) -> CleanupManifest:
    if not path.is_file():
        raise E2EValidationError("cleanup manifest not found")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = CleanupManifest(
            version=int(raw["version"]),
            run_id=str(raw["run_id"]),
            b_user_id=str(raw["b_user_id"]),
            b_session_id=str(raw["b_session_id"]),
            notification_ids=[int(item) for item in raw["notification_ids"]],
            created_at=str(raw["created_at"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise E2EValidationError("cleanup manifest is invalid") from exc
    if (
        manifest.version != 1
        or not manifest.b_user_id.startswith(E2E_USER_PREFIX)
        or not manifest.b_session_id.startswith(E2E_SESSION_PREFIX)
    ):
        raise E2EValidationError("cleanup manifest does not describe this E2E scenario")
    return manifest


def _select_open_requests(db: Any, request_id: int | None) -> list[PartnerRequest]:
    statement = select(PartnerRequest).where(
        PartnerRequest.status == "OPEN",
        PartnerRequest.normalized_activity == ACTIVITY,
        PartnerRequest.expires_at > _utcnow(),
    )
    if request_id is not None:
        statement = statement.where(PartnerRequest.id == request_id)
    statement = statement.order_by(PartnerRequest.id)
    return list(db.scalars(statement))


def _find_open_request(db: Any, request_id: int | None) -> PartnerRequest:
    requests = _select_open_requests(db, request_id)
    if not requests:
        raise E2EValidationError("no active OPEN frisbee request was found")
    if len(requests) > 1:
        raise E2EValidationError(
            "multiple active OPEN frisbee requests found; rerun with --request-id"
        )
    return requests[0]


def _validate_real_requester(requester: User) -> None:
    if requester.is_mock:
        raise E2EValidationError("the selected request belongs to a mock user")
    if not requester.wechat_openid:
        raise E2EValidationError("the selected requester is not a WeChat user")
    if not requester.verified or not requester.recommendation_enabled:
        raise E2EValidationError("the selected requester is not recommendation-eligible")


def _candidate_availability(requested: Any = None) -> list[str]:
    """Keep the canonical slot while mirroring safe request-time tokens.

    Agent parsing may persist ``["下午"]`` or ``["周六", "下午"]`` for the
    same natural-language slot represented by the E2E profile as
    ``["周六下午"]``.  Production hard filtering intentionally uses exact
    normalized-tag overlap, so the synthetic candidate must advertise the
    selected request's stored tokens as well as the canonical E2E slot.
    """

    if isinstance(requested, str):
        requested_values = [requested]
    elif isinstance(requested, (list, tuple, set)):
        requested_values = [item for item in requested if isinstance(item, str)]
    else:
        requested_values = []
    return list(dict.fromkeys([AVAILABILITY, *requested_values]))


def _build_candidate(run_id: str, *, requested_availability: Any = None) -> User:
    user_id = f"{E2E_USER_PREFIX}{run_id}"
    return User(
        id=user_id,
        nickname=E2E_NICKNAME,
        school_email=f"{user_id}@{E2E_EMAIL_DOMAIN}",
        wechat_openid=None,
        school_uid=None,
        school_display_name="E2E 临时用户",
        identity_provider=E2E_IDENTITY_PROVIDER,
        school="中国科学技术大学",
        campus=CAMPUS,
        grade="研一",
        major="E2E测试",
        bio="一次性双用户 E2E 测试账号，验证后清理。",
        social_goals=["运动搭子", "活动伙伴"],
        interests=[ACTIVITY],
        activities=[ACTIVITY],
        availability=_candidate_availability(requested_availability),
        social_style="随和",
        avoidances=[],
        recommendation_enabled=True,
        verified=True,
        campus_verified=True,
        personality_consent=False,
        personality_traits={},
        personality_summary="",
        password_hash=None,
        token_version=0,
        is_mock=False,
    )


def _has_exact_activity(user: User, activity: str) -> bool:
    desired = normalize_tag(activity)
    return desired in {normalize_tag(item) for item in (user.activities or [])}


def _intent_payload(request: PartnerRequest) -> dict[str, Any]:
    raw = request.intent
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(decoded) if isinstance(decoded, dict) else {}
    return {}


def _verify_production_matching(
    db: Any,
    request: PartnerRequest,
    requester: User,
    candidate: User,
) -> bool:
    """Verify both the waiting request and later-request production directions."""

    engine = MatchingEngine(db)

    # A -> B: B must satisfy the exact intent stored with A's OPEN request.
    request_intent = _intent_payload(request)
    accepted_for_a, _ = engine.filter_candidates(
        requester, [candidate], request_intent
    )
    if candidate not in accepted_for_a or not _has_exact_activity(candidate, ACTIVITY):
        return False
    engine.rank_candidates(requester, accepted_for_a, request_intent)

    # B -> A: this mirrors the later user's actual matching result which feeds
    # PartnerLoopService.record_request(candidate_ids=...).  Availability is on
    # B's profile; omitting it from the new intent avoids rewriting A's profile.
    later_intent = {"activity": ACTIVITY, "availability": []}
    accepted_for_b, _ = engine.filter_candidates(candidate, [requester], later_intent)
    if requester not in accepted_for_b or not _has_exact_activity(requester, ACTIVITY):
        return False
    ranked_for_b = engine.rank_candidates(candidate, accepted_for_b, later_intent)
    return any(item["candidate"].id == requester.id for item in ranked_for_b)


def _safe_request_fields(request: PartnerRequest) -> dict[str, str]:
    intent = _intent_payload(request)
    availability = intent.get("availability") or []
    return {
        "request_id": str(request.id),
        "activity": str(request.normalized_activity or intent.get("activity") or ""),
        "campus": str(intent.get("campus") or "未指定"),
        "availability": "、".join(str(item) for item in availability) or "未指定",
        "status": request.status,
        "created_at": request.created_at.isoformat(),
    }


def _print_safe_request(request: PartnerRequest, *, include_created_at: bool) -> None:
    fields = _safe_request_fields(request)
    print(f"request id: {fields['request_id']}")
    print(f"activity: {fields['activity']}")
    print(f"campus: {fields['campus']}")
    print(f"availability: {fields['availability']}")
    if include_created_at:
        print(f"created_at: {fields['created_at']}")


def dry_run_e2e(
    db: Any, *, request_id: int | None, manifest_path: Path
) -> int:
    """Read-only request selection and production matching preflight."""

    requests = _stage_call(
        "prepare_request", lambda: _select_open_requests(db, request_id)
    )
    if not requests:
        print("A request found: no")
        print("database changes made: no")
        return 2
    if len(requests) > 1:
        print("A request found: multiple")
        for index, request in enumerate(requests):
            if index:
                print("---")
            _print_safe_request(request, include_created_at=True)
        print(
            "Rerun with: ./.venv/bin/python scripts/e2e_partner_loop.py "
            "--request-id ID"
        )
        print("database changes made: no")
        return 2

    request = requests[0]
    print("A request found: yes")
    _print_safe_request(request, include_created_at=False)
    print(f"status: {request.status}")

    request_valid = False
    b_would_be_created = False
    requester = _stage_call(
        "prepare_request", lambda: db.get(User, request.user_id)
    )
    if requester is not None:
        try:
            _stage_call(
                "prepare_request", lambda: _validate_real_requester(requester)
            )
            request_intent = _intent_payload(request)
            candidate = _stage_call(
                "create_candidate",
                lambda: _build_candidate(
                    f"dryrun-{uuid4().hex[:8]}",
                    requested_availability=request_intent.get("availability"),
                ),
            )
            request_valid = _stage_call(
                "matching",
                lambda: _verify_production_matching(
                    db, request, requester, candidate
                ),
            )
            b_would_be_created = bool(
                request_valid
                and not manifest_path.exists()
                and _stage_call(
                    "create_candidate", lambda: db.get(User, candidate.id)
                )
                is None
            )
        except E2EValidationError:
            request_valid = False
    print(f"request valid: {'yes' if request_valid else 'no'}")
    print(f"B would be created: {'yes' if b_would_be_created else 'no'}")
    print("database changes made: no")
    return 0 if request_valid and b_would_be_created else 2


def _notices_for_source(db: Any, source_session_id: str) -> list[Notification]:
    notices = list(
        db.scalars(select(Notification).where(Notification.kind == NOTICE_KIND))
    )
    return [
        item
        for item in notices
        if (item.payload or {}).get("source_session_id") == source_session_id
    ]


def execute_e2e(
    db: Any, *, request_id: int | None, manifest_path: Path
) -> E2ESummary:
    """Execute the marked E2E setup without exposing requester identifiers."""

    summary = E2ESummary()
    if manifest_path.exists():
        raise E2EValidationError(
            "cleanup manifest already exists; run --cleanup before another E2E run"
        )

    request = _stage_call(
        "prepare_request", lambda: _find_open_request(db, request_id)
    )
    summary.request_found = True
    requester = _stage_call(
        "prepare_request", lambda: db.get(User, request.user_id)
    )
    if requester is None:
        raise E2EValidationError("the OPEN request owner no longer exists")
    _stage_call("prepare_request", lambda: _validate_real_requester(requester))

    run_id = uuid4().hex[:12]
    request_intent = _intent_payload(request)
    candidate = _stage_call(
        "create_candidate",
        lambda: _build_candidate(
            run_id,
            requested_availability=request_intent.get("availability"),
        ),
    )
    summary.match_eligible = _stage_call(
        "matching",
        lambda: _verify_production_matching(db, request, requester, candidate),
    )
    if not summary.match_eligible:
        raise E2EValidationError(
            "the synthetic candidate did not pass the existing production matching rules"
        )

    source_session_id = f"{E2E_SESSION_PREFIX}{run_id}"
    manifest = CleanupManifest(
        version=1,
        run_id=run_id,
        b_user_id=candidate.id,
        b_session_id=source_session_id,
        notification_ids=[],
        created_at=_utcnow().isoformat(),
    )
    # Write the cleanup scope before the first database mutation so an
    # interrupted run remains recoverable.
    _stage_call(
        "cleanup_manifest",
        lambda: _write_manifest(manifest_path, manifest, replace=False),
    )

    def create_candidate() -> tuple[User | None, set[str]]:
        db.add(candidate)
        db.commit()
        created_candidate = db.get(User, candidate.id)
        candidate_ids = {
            item.id for item in MatchingEngine(db).retrieve_candidates(requester.id)
        }
        return created_candidate, candidate_ids

    created, retrievable_ids = _stage_call("create_candidate", create_candidate)
    summary.candidate_created = bool(
        created is not None
        and created.is_mock is False
        and created.wechat_openid is None
        and created.identity_provider == E2E_IDENTITY_PROVIDER
        and created.id in retrievable_ids
    )
    if not summary.candidate_created:
        raise E2EValidationError("the synthetic candidate was not created safely")

    # This is the same production service call made by CampusSocialAgent after
    # a later user's real matching result.  Notification rows are never inserted
    # directly by this script.
    _stage_call(
        "create_notification",
        lambda: PartnerLoopService(db).record_request(
            candidate.id,
            source_session_id,
            {"activity": ACTIVITY, "availability": []},
            [requester.id],
        ),
    )

    notices = _stage_call(
        "create_notification", lambda: _notices_for_source(db, source_session_id)
    )
    summary.notification_created = bool(notices)
    summary.notification_recipient_is_a = bool(notices) and all(
        item.user_id == request.user_id for item in notices
    )
    updated_manifest = CleanupManifest(
        **{
            **asdict(manifest),
            "notification_ids": [item.id for item in notices],
        }
    )
    _stage_call(
        "cleanup_manifest",
        lambda: _write_manifest(manifest_path, updated_manifest, replace=True),
    )
    return summary


def _validate_cleanup_candidate(candidate: User) -> None:
    email = candidate.school_email or ""
    if not (
        candidate.id.startswith(E2E_USER_PREFIX)
        and candidate.nickname == E2E_NICKNAME
        and candidate.identity_provider == E2E_IDENTITY_PROVIDER
        and email.endswith(f"@{E2E_EMAIL_DOMAIN}")
        and candidate.wechat_openid is None
        and candidate.is_mock is False
    ):
        raise E2EValidationError("cleanup refused: user no longer has exact E2E markers")


def cleanup_e2e(db: Any, *, manifest_path: Path) -> dict[str, bool]:
    """Delete only rows tied to the manifest's exact marked B/session scope."""

    manifest = _load_manifest(manifest_path)
    candidate = db.get(User, manifest.b_user_id)
    if candidate is not None:
        _validate_cleanup_candidate(candidate)

    discovered_notices = _notices_for_source(db, manifest.b_session_id)
    safe_notice_ids = {
        item.id
        for item in discovered_notices
        if item.id in set(manifest.notification_ids) or not manifest.notification_ids
    }
    # A notification may have been created just before an interrupted manifest
    # update.  Its unguessable source session is the authoritative cleanup tag.
    safe_notice_ids.update(item.id for item in discovered_notices)
    if safe_notice_ids:
        db.execute(delete(Notification).where(Notification.id.in_(safe_notice_ids)))
    db.execute(
        delete(Notification).where(Notification.user_id == manifest.b_user_id)
    )
    db.execute(
        delete(Message).where(
            or_(
                Message.sender_id == manifest.b_user_id,
                Message.recipient_id == manifest.b_user_id,
            )
        )
    )
    db.execute(
        delete(Interaction).where(
            or_(
                Interaction.actor_id == manifest.b_user_id,
                Interaction.target_id == manifest.b_user_id,
            )
        )
    )
    db.execute(
        delete(Match).where(
            or_(
                Match.user_a_id == manifest.b_user_id,
                Match.user_b_id == manifest.b_user_id,
            )
        )
    )
    db.execute(
        delete(Block).where(
            or_(
                Block.blocker_id == manifest.b_user_id,
                Block.blocked_id == manifest.b_user_id,
            )
        )
    )
    db.execute(
        delete(Report).where(
            or_(
                Report.reporter_id == manifest.b_user_id,
                Report.reported_id == manifest.b_user_id,
            )
        )
    )
    db.execute(delete(Preference).where(Preference.user_id == manifest.b_user_id))
    db.execute(
        delete(AgentTraceRecord).where(
            AgentTraceRecord.user_id == manifest.b_user_id
        )
    )
    db.execute(
        delete(AgentSessionRecord).where(
            AgentSessionRecord.user_id == manifest.b_user_id
        )
    )
    db.execute(
        delete(PartnerRequest).where(
            PartnerRequest.user_id == manifest.b_user_id
        )
    )
    db.execute(delete(User).where(User.id == manifest.b_user_id))
    db.commit()

    candidate_removed = db.get(User, manifest.b_user_id) is None
    notification_removed = not _notices_for_source(db, manifest.b_session_id)
    if not candidate_removed or not notification_removed:
        raise E2EValidationError("cleanup verification failed; manifest was preserved")
    manifest_path.unlink()
    return {
        "candidate_removed": candidate_removed,
        "notification_removed": notification_removed,
        "manifest_removed": not manifest_path.exists(),
    }


def _print_summary(summary: E2ESummary) -> None:
    print(f"A request found: {'yes' if summary.request_found else 'no'}")
    print(f"B candidate created: {'yes' if summary.candidate_created else 'no'}")
    print(f"match eligible: {'yes' if summary.match_eligible else 'no'}")
    print(
        "notification created: "
        f"{'yes' if summary.notification_created else 'no'}"
    )
    print(
        "notification recipient is A: "
        f"{'yes' if summary.notification_recipient_is_a else 'no'}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Private one-time real-A + synthetic-B partner-loop E2E"
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--execute", action="store_true", help="create B and run production matching"
    )
    action.add_argument(
        "--cleanup", action="store_true", help="remove the exact manifest-scoped run"
    )
    parser.add_argument(
        "--request-id",
        type=int,
        help="select one OPEN frisbee request when more than one exists",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="local cleanup manifest path (default: .e2e/partner-loop.json)",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    settings = get_settings()
    try:
        with SessionLocal() as db:
            if not args.execute and not args.cleanup:
                return dry_run_e2e(
                    db, request_id=args.request_id, manifest_path=args.manifest
                )
            if settings.data_backend != "cloudbase_http":
                print(
                    "Refused: DATA_BACKEND must be cloudbase_http for the phone E2E run."
                )
                return 2
            if args.cleanup:
                result = _stage_call(
                    "cleanup_manifest",
                    lambda: cleanup_e2e(db, manifest_path=args.manifest),
                )
                print(
                    "B candidate removed: "
                    f"{'yes' if result['candidate_removed'] else 'no'}"
                )
                print(
                    "E2E notification removed: "
                    f"{'yes' if result['notification_removed'] else 'no'}"
                )
                print(
                    "cleanup manifest removed: "
                    f"{'yes' if result['manifest_removed'] else 'no'}"
                )
                return 0
            summary = execute_e2e(
                db, request_id=args.request_id, manifest_path=args.manifest
            )
            _print_summary(summary)
            if not (
                summary.notification_created
                and summary.notification_recipient_is_a
            ):
                return 2
            print("Keep the manifest until phone verification, then run --cleanup.")
            return 0
    except E2EValidationError as exc:
        print(f"E2E precondition failed: {exc}")
        return 2
    except E2EStageError as exc:
        _print_stage_error(exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI must not dump secret-bearing context
        _print_stage_error(E2EStageError("prepare_request", exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
