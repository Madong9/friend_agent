from __future__ import annotations

from ..models import User


def public_user(user: User) -> dict:
    """Single allow-list prevents accidental exposure of future private columns."""
    return {
        "id": user.id,
        "nickname": user.nickname,
        "school": user.school,
        "campus": user.campus,
        "grade": user.grade,
        "major": user.major,
        "bio": user.bio,
        "social_goals": list(user.social_goals),
        "interests": list(user.interests),
        "activities": list(user.activities),
        "availability": list(user.availability),
        "social_style": user.social_style,
        "campus_verified": bool(user.campus_verified),
        "personality_traits": dict(user.personality_traits or {}),
        "personality_summary": user.personality_summary or "",
        "is_mock": bool(user.is_mock),
    }
