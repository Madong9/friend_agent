#!/usr/bin/env python3
"""Print a privacy-preserving closed-beta metrics snapshot as JSON.

The script works with both local SQLite and the CloudBase HTTP repository. It
only emits aggregate counts and rates; it never prints user identifiers,
messages, prompts, personality text, or credentials.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models import (  # noqa: E402
    Interaction,
    Match,
    Message,
    Notification,
    PartnerRequest,
    Report,
    User,
)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _count(db, model, *criteria) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return int(db.scalar(statement) or 0)


def snapshot(db) -> dict:
    users = list(db.scalars(select(User).where(User.is_mock.is_(False))))
    profile_complete = sum(
        bool(
            user.nickname
            and user.campus not in {"", "待完善", "待验证"}
            and user.grade not in {"", "待完善"}
            and user.major not in {"", "待完善"}
            and user.activities
            and user.availability
        )
        for user in users
    )
    requests = list(db.scalars(select(PartnerRequest)))
    request_statuses = Counter(item.status for item in requests)
    interactions = list(db.scalars(select(Interaction)))
    feedback_counts = Counter(
        item.kind for item in interactions if item.kind in {"LIKE", "PASS", "NOT_RELEVANT"}
    )

    activity_dates: dict[str, set] = defaultdict(set)
    for item in interactions:
        if item.created_at:
            activity_dates[item.actor_id].add(item.created_at.date())
    next_day_return_users = 0
    for dates in activity_dates.values():
        first = min(dates)
        if first + timedelta(days=1) in dates:
            next_day_return_users += 1

    total_requests = len(requests)
    fulfilled_requests = request_statuses["FULFILLED"]
    total_feedback = sum(feedback_counts.values())
    real_users = len(users)
    return {
        "users": {
            "all": _count(db, User),
            "real": real_users,
            "campus_verified_real": sum(bool(user.campus_verified) for user in users),
            "profile_complete_real": profile_complete,
            "profile_completion_rate": _rate(profile_complete, real_users),
            "personality_opt_in_real": sum(
                bool(user.personality_consent) for user in users
            ),
        },
        "partner_requests": {
            "all": total_requests,
            "open": request_statuses["OPEN"],
            "fulfilled": fulfilled_requests,
            "paused": request_statuses["PAUSED"],
            "expired": request_statuses["EXPIRED"],
            "fulfilled_rate": _rate(fulfilled_requests, total_requests),
        },
        "feedback": {
            "like": feedback_counts["LIKE"],
            "pass": feedback_counts["PASS"],
            "not_relevant": feedback_counts["NOT_RELEVANT"],
            "like_rate": _rate(feedback_counts["LIKE"], total_feedback),
        },
        "social": {
            "mutual_matches": _count(db, Match, Match.status == "MATCHED"),
            "messages": _count(db, Message),
            "unread_notifications": _count(
                db, Notification, Notification.read_at.is_(None)
            ),
            "pending_reports": _count(db, Report, Report.status == "PENDING"),
        },
        "retention": {
            "users_with_recorded_events": len(activity_dates),
            "next_day_return_users": next_day_return_users,
            "next_day_return_rate": _rate(
                next_day_return_users, len(activity_dates)
            ),
            "definition": "首次记录交互后的下一个自然日再次产生交互",
        },
    }


def main() -> None:
    with SessionLocal() as db:
        print(json.dumps(snapshot(db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
