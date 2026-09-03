from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models import Block, Interaction, User
from .similarity import normalize_tag, normalized_set


STRONG_REJECTIONS = {"NOT_RELEVANT", "BLOCK", "REPORT"}


def hard_filter_reason(
    db: Session, user: User, candidate: User, intent: dict
) -> str | None:
    if candidate.id == user.id:
        return "self"
    if not candidate.recommendation_enabled:
        return "recommendation_disabled"
    if not candidate.verified:
        return "not_verified"
    # Email/CAS users carry a school email; mini-program users carry a
    # server-verified WeChat openid. Requiring email here would make every real
    # WeChat beta user permanently invisible to recommendations.
    if candidate.school_email is None and candidate.wechat_openid is None:
        return "not_school_identity"

    blocked = db.scalar(
        select(Block.id).where(
            or_(
                and_(Block.blocker_id == user.id, Block.blocked_id == candidate.id),
                and_(Block.blocker_id == candidate.id, Block.blocked_id == user.id),
            )
        )
    )
    if blocked:
        return "blocked_relation"

    rejected = db.scalar(
        select(Interaction.id).where(
            Interaction.actor_id == user.id,
            Interaction.target_id == candidate.id,
            Interaction.kind.in_(STRONG_REJECTIONS),
        )
    )
    if rejected:
        return "previous_strong_rejection"

    campus = intent.get("campus")
    if campus and "campus" in intent.get("hard_constraints", []):
        if normalize_tag(candidate.campus) != normalize_tag(campus):
            return "campus_constraint"

    requested_times = intent.get("availability", [])
    if requested_times and not (
        normalized_set(requested_times) & normalized_set(candidate.availability)
    ):
        return "time_conflict"

    goal = intent.get("goal")
    compatible = {
        "find_activity_partner": {"运动搭子", "兴趣朋友", "活动伙伴"},
        "find_study_partner": {"学习搭子", "考研搭子"},
    }.get(goal)
    if compatible and normalized_set(candidate.social_goals).isdisjoint(
        normalized_set(compatible)
    ):
        return "incompatible_social_goal"
    return None
