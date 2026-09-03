from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User
from .filters import hard_filter_reason
from .scorer import score_candidate


class MatchingEngine:
    def __init__(self, db: Session):
        self.db = db

    def retrieve_candidates(self, user_id: str) -> list[User]:
        statement = select(User).where(User.id != user_id)
        if not get_settings().show_mock_users:
            statement = statement.where(User.is_mock.is_(False))
        return list(self.db.scalars(statement))

    def filter_candidates(
        self, user: User, candidates: list[User], intent: dict
    ) -> tuple[list[User], dict[str, str]]:
        accepted: list[User] = []
        rejected: dict[str, str] = {}
        for candidate in candidates:
            reason = hard_filter_reason(self.db, user, candidate, intent)
            if reason:
                rejected[candidate.id] = reason
            else:
                accepted.append(candidate)
        return accepted, rejected

    def rank_candidates(
        self,
        user: User,
        candidates: list[User],
        intent: dict,
        feedback_by_candidate: dict[str, float] | None = None,
    ) -> list[dict]:
        feedback_by_candidate = feedback_by_candidate or {}
        ranked = []
        for candidate in candidates:
            result = score_candidate(
                user, candidate, intent, feedback_by_candidate.get(candidate.id, 0.5)
            )
            ranked.append({"candidate": candidate, "score": result})
        return sorted(
            ranked, key=lambda item: (-item["score"].total, item["candidate"].id)
        )

    def recommend(self, user_id: str, intent: dict, limit: int = 3) -> list[dict]:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"user not found: {user_id}")
        candidates, _ = self.filter_candidates(
            user, self.retrieve_candidates(user_id), intent
        )
        return self.rank_candidates(user, candidates, intent)[:limit]
