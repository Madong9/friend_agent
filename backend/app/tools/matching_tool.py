from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..matching import MatchingEngine
from ..memory import MemoryManager
from ..models import User
from .base import BaseTool
from .privacy import public_user


class MatchingToolInput(BaseModel):
    action: Literal["search_candidates", "rank_candidates"]
    user_id: str
    intent: dict = Field(default_factory=dict)
    candidate_ids: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=100)


class MatchingTool(BaseTool):
    name = "MatchingTool"
    description = "Deterministically retrieve, hard-filter, score and rank candidates."
    input_schema = MatchingToolInput

    def __init__(self, db: Session):
        self.db = db
        self.engine = MatchingEngine(db)
        self.memory = MemoryManager(db)

    async def execute(self, tool_input: MatchingToolInput) -> dict:
        user = self.db.get(User, tool_input.user_id)
        if user is None:
            raise ValueError(f"user not found: {tool_input.user_id}")
        if tool_input.action == "search_candidates":
            raw = self.engine.retrieve_candidates(user.id)
            accepted, rejected = self.engine.filter_candidates(
                user, raw, tool_input.intent
            )
            recent = set(self.memory.get_recent_candidates(user.id))
            # PASS and the immediately preceding recommendation are temporarily suppressed.
            accepted = [
                candidate for candidate in accepted if candidate.id not in recent
            ]
            return {
                "candidate_ids": [candidate.id for candidate in accepted],
                "candidates": [public_user(candidate) for candidate in accepted],
                "retrieved_count": len(raw),
                "filtered_count": len(accepted),
                "filter_reasons": rejected,
            }
        candidates = [
            self.db.get(User, candidate_id) for candidate_id in tool_input.candidate_ids
        ]
        valid = [candidate for candidate in candidates if candidate is not None]
        ranked = self.engine.rank_candidates(
            user,
            valid,
            tool_input.intent,
            self.memory.ranking_feedback_adjustments(user.id, valid),
        )[: tool_input.limit]
        return {
            "ranked": [
                {**public_user(item["candidate"]), **item["score"].to_dict()}
                for item in ranked
            ]
        }
