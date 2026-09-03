from __future__ import annotations

from dataclasses import asdict, dataclass

from ..models import User
from .similarity import (
    JaccardSimilarity,
    availability_similarity,
    containment_similarity,
    normalize_tag,
    normalized_set,
)


WEIGHTS = {
    "interest": 0.25,
    "activity": 0.20,
    "availability": 0.20,
    "social_goal": 0.15,
    "location": 0.10,
    "feedback": 0.10,
}

PERSONALITY_DIMENSIONS = (
    "energy",
    "planning",
    "communication",
    "group_preference",
    "connection_pace",
)


def personality_compatibility(left: dict, right: dict) -> float | None:
    if not left or not right:
        return None
    scores = []
    for dimension in PERSONALITY_DIMENSIONS:
        left_value = left.get(dimension)
        right_value = right.get(dimension)
        if not left_value or not right_value:
            continue
        if left_value == right_value:
            scores.append(1.0)
        elif "balanced" in {left_value, right_value}:
            scores.append(0.85)
        else:
            scores.append(0.65)
    return sum(scores) / len(scores) if scores else None


@dataclass(frozen=True)
class MatchScore:
    total: float
    features: dict[str, float]
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def score_candidate(
    user: User,
    candidate: User,
    intent: dict,
    feedback_adjustment: float = 0.5,
) -> MatchScore:
    sim = JaccardSimilarity()
    activity = intent.get("activity")
    desired_times = intent.get("availability") or user.availability
    requested_goal = intent.get("goal")
    goal_tags = {
        "find_activity_partner": ["运动搭子", "活动伙伴"],
        "find_study_partner": ["学习搭子"],
        "find_interest_friend": ["兴趣朋友"],
    }.get(requested_goal, user.social_goals)

    activity_score = (
        containment_similarity([activity], candidate.activities)
        if activity
        else sim.similarity(user.activities, candidate.activities)
    )
    if requested_goal:
        social_goal_score = (
            1.0
            if normalized_set(goal_tags) & normalized_set(candidate.social_goals)
            else 0.0
        )
    else:
        social_goal_score = sim.similarity(user.social_goals, candidate.social_goals)
    features = {
        "interest": sim.similarity(user.interests, candidate.interests),
        "activity": activity_score,
        "availability": availability_similarity(desired_times, candidate.availability),
        "social_goal": social_goal_score,
        "location": 1.0
        if normalize_tag(intent.get("campus") or user.campus)
        == normalize_tag(candidate.campus)
        else 0.0,
        "feedback": max(0.0, min(1.0, feedback_adjustment)),
    }
    personality_score = personality_compatibility(
        user.personality_traits or {}, candidate.personality_traits or {}
    )
    features["personality"] = personality_score if personality_score is not None else 0.5
    base_total = sum(features[key] * WEIGHTS[key] for key in WEIGHTS)
    total = round(
        0.9 * base_total + 0.1 * personality_score
        if personality_score is not None
        else base_total,
        4,
    )

    common_interests = sorted(set(user.interests) & set(candidate.interests))
    reasons: list[str] = []
    if common_interests:
        reasons.append(f"共同兴趣：{'、'.join(common_interests[:3])}")
    if features["activity"] > 0:
        reasons.append(f"都愿意参加{activity or '相关活动'}")
    if features["availability"] > 0:
        reasons.append("可用时间有重合")
    if features["location"] == 1:
        reasons.append(f"都在{candidate.campus}")
    if features["social_goal"] > 0:
        reasons.append("社交目标相近")
    if personality_score is not None and personality_score >= 0.8:
        reasons.append("公开社交风格较合拍")
    return MatchScore(
        total=total,
        features={k: round(v, 4) for k, v in features.items()},
        reasons=reasons,
    )
