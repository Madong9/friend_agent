from __future__ import annotations

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from ..memory import MemoryManager
from ..models import Block, Interaction, Match, Report, User


class SocialService:
    USER_DECISIONS = {"LIKE", "INTERESTED", "PASS", "NOT_RELEVANT", "BLOCK", "REPORT"}
    POSITIVE_DECISIONS = {"LIKE", "INTERESTED"}

    def __init__(self, db: Session):
        self.db = db
        self.memory = MemoryManager(db)

    def _require_pair(self, user_id: str, candidate_id: str) -> None:
        if user_id == candidate_id:
            raise ValueError("cannot interact with self")
        if (
            self.db.get(User, user_id) is None
            or self.db.get(User, candidate_id) is None
        ):
            raise ValueError("user not found")

    def _is_blocked(self, user_id: str, candidate_id: str) -> bool:
        return (
            self.db.scalar(
                select(Block.id).where(
                    or_(
                        and_(
                            Block.blocker_id == user_id,
                            Block.blocked_id == candidate_id,
                        ),
                        and_(
                            Block.blocker_id == candidate_id,
                            Block.blocked_id == user_id,
                        ),
                    )
                )
            )
            is not None
        )

    def _latest_decision(self, actor_id: str, target_id: str) -> str | None:
        return self.db.scalar(
            select(Interaction.kind)
            .where(
                Interaction.actor_id == actor_id,
                Interaction.target_id == target_id,
                Interaction.kind.in_(self.USER_DECISIONS),
            )
            .order_by(desc(Interaction.created_at), desc(Interaction.id))
            .limit(1)
        )

    def block_user(self, user_id: str, blocked_user_id: str) -> Block:
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_block_user",
                {"p_user_id": user_id, "p_blocked_user_id": blocked_user_id},
            )
            if result.get("status") != "blocked":
                raise ValueError(result.get("status") or "block failed")
            block = self.db.get(Block, result["block_id"])
            if block is None:
                raise RuntimeError("block transaction returned no row")
            return block
        self._require_pair(user_id, blocked_user_id)
        block = self.db.scalar(
            select(Block).where(
                Block.blocker_id == user_id, Block.blocked_id == blocked_user_id
            )
        )
        if block is None:
            block = Block(blocker_id=user_id, blocked_id=blocked_user_id)
            self.db.add(block)
            self.db.add(
                Interaction(
                    actor_id=user_id,
                    target_id=blocked_user_id,
                    kind="BLOCK",
                    payload={},
                )
            )

        user_a, user_b = sorted((user_id, blocked_user_id))
        match = self.db.scalar(
            select(Match).where(Match.user_a_id == user_a, Match.user_b_id == user_b)
        )
        if match is not None:
            match.status = "BLOCKED"
        self.db.commit()
        self.db.refresh(block)
        return block

    def report_user(
        self,
        user_id: str,
        reported_user_id: str,
        reason: str,
        category: str = "OTHER",
    ) -> Report:
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_report_user",
                {
                    "p_user_id": user_id,
                    "p_reported_user_id": reported_user_id,
                    "p_reason": reason,
                    "p_category": category,
                },
            )
            if result.get("status") != "reported":
                raise ValueError(result.get("status") or "report failed")
            report = self.db.get(Report, result["report_id"])
            if report is None:
                raise RuntimeError("report transaction returned no row")
            return report
        self._require_pair(user_id, reported_user_id)
        report = Report(
            reporter_id=user_id,
            reported_id=reported_user_id,
            reason=reason,
            category=category,
        )
        self.db.add(report)
        self.db.add(
            Interaction(
                actor_id=user_id,
                target_id=reported_user_id,
                kind="REPORT",
                    payload={"reason": reason, "category": category},
            )
        )
        self.db.commit()
        self.db.refresh(report)
        return report

    def record_feedback(
        self, user_id: str, candidate_id: str, feedback: str
    ) -> Match | None:
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_record_feedback",
                {
                    "p_user_id": user_id,
                    "p_candidate_id": candidate_id,
                    "p_feedback": feedback,
                },
            )
            if result.get("status") != "recorded":
                raise ValueError(result.get("status") or "feedback failed")
            match_id = result.get("match_id")
            return self.db.get(Match, match_id) if match_id is not None else None
        self._require_pair(user_id, candidate_id)
        if feedback == "BLOCK":
            self.block_user(user_id, candidate_id)
            return None
        if self._is_blocked(user_id, candidate_id):
            raise ValueError("blocked relation")
        self.memory.record_feedback(user_id, candidate_id, feedback)
        candidate = self.db.get(User, candidate_id)
        if candidate is not None:
            self.memory.learn_candidate_preferences(user_id, candidate, feedback)
        if feedback not in self.POSITIVE_DECISIONS:
            return None

        reciprocal = self._latest_decision(candidate_id, user_id)
        if reciprocal not in self.POSITIVE_DECISIONS:
            return None
        user_a, user_b = sorted((user_id, candidate_id))
        match = self.db.scalar(
            select(Match).where(Match.user_a_id == user_a, Match.user_b_id == user_b)
        )
        if match is None:
            match = Match(user_a_id=user_a, user_b_id=user_b, status="MATCHED")
            self.db.add(match)
            self.db.add_all(
                [
                    Interaction(
                        actor_id=user_id,
                        target_id=candidate_id,
                        kind="MATCHED",
                        payload={},
                    ),
                    Interaction(
                        actor_id=candidate_id,
                        target_id=user_id,
                        kind="MATCHED",
                        payload={},
                    ),
                ]
            )
            self.db.commit()
            self.db.refresh(match)
        return match

    def list_matches(self, user_id: str) -> list[Match]:
        return list(
            self.db.scalars(
                select(Match).where(
                    Match.status == "MATCHED",
                    or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
                )
            )
        )
