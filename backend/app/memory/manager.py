"""Persistent profile/preference/interaction memory plus short-lived session memory."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AgentSessionRecord, Interaction, Preference, User


FEEDBACK_SIGNAL = {
    "LIKE": 0.08,
    "INTERESTED": 0.10,
    "CHATTED": 0.08,
    "MET": 0.12,
    "PASS": -0.04,
    "NOT_RELEVANT": -0.15,
}


class SessionBusyError(RuntimeError):
    pass


class MemoryManager:
    def __init__(self, db: Session, session_ttl: timedelta | None = None):
        self.db = db
        self.session_ttl = session_ttl or timedelta(
            minutes=get_settings().agent_session_ttl_minutes
        )

    def load_user_memory(self, user_id: str) -> dict[str, Any]:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError(f"user not found: {user_id}")
        preferences = list(
            self.db.scalars(select(Preference).where(Preference.user_id == user_id))
        )
        interactions = list(
            self.db.scalars(
                select(Interaction)
                .where(Interaction.actor_id == user_id)
                .order_by(desc(Interaction.created_at))
                .limit(50)
            )
        )
        return {
            "profile": {
                "id": user.id,
                "nickname": user.nickname,
                "campus": user.campus,
                "grade": user.grade,
                "major": user.major,
                "bio": user.bio,
                "social_goals": user.social_goals,
                "interests": user.interests,
                "activities": user.activities,
                "availability": user.availability,
                "social_style": user.social_style,
                "avoidances": user.avoidances,
                "is_mock": user.is_mock,
            },
            "preferences": {
                item.key: {"value": item.value, "weight": item.weight}
                for item in preferences
            },
            "interactions": [
                {
                    "target_id": item.target_id,
                    "kind": item.kind,
                    "payload": item.payload,
                    "created_at": item.created_at.isoformat(),
                }
                for item in interactions
            ],
        }

    def record_feedback(
        self, user_id: str, candidate_id: str, feedback: str
    ) -> Interaction:
        interaction = Interaction(
            actor_id=user_id, target_id=candidate_id, kind=feedback, payload={}
        )
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    def record_recommendation(
        self, user_id: str, candidate_ids: list[str], session_id: str
    ) -> None:
        for candidate_id in candidate_ids:
            self.db.add(
                Interaction(
                    actor_id=user_id,
                    target_id=candidate_id,
                    kind="RECOMMENDED",
                    payload={"session_id": session_id},
                )
            )
        self.db.commit()

    def update_preference(
        self, user_id: str, key: str, value: str, signal: float
    ) -> Preference:
        preference = self.db.scalar(
            select(Preference).where(
                Preference.user_id == user_id, Preference.key == key
            )
        )
        bounded_signal = max(-0.25, min(0.25, signal))
        if preference is None:
            preference = Preference(
                user_id=user_id, key=key, value=value, weight=bounded_signal
            )
            self.db.add(preference)
        else:
            # 80% history + 20% new evidence prevents one click dominating future ranking.
            preference.value = value
            preference.weight = max(
                -0.25, min(0.25, 0.8 * preference.weight + 0.2 * bounded_signal)
            )
            preference.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def feedback_adjustments(self, user_id: str) -> dict[str, float]:
        interactions = list(
            self.db.scalars(
                select(Interaction)
                .where(
                    Interaction.actor_id == user_id, Interaction.target_id.is_not(None)
                )
                .order_by(desc(Interaction.created_at))
                .limit(100)
            )
        )
        totals: defaultdict[str, float] = defaultdict(float)
        counts: defaultdict[str, int] = defaultdict(int)
        for item in interactions:
            signal = FEEDBACK_SIGNAL.get(item.kind)
            if signal is None or item.target_id is None:
                continue
            decay = 0.85 ** counts[item.target_id]
            totals[item.target_id] += signal * decay
            counts[item.target_id] += 1
        return {
            target_id: max(0.25, min(0.75, 0.5 + signal))
            for target_id, signal in totals.items()
        }

    def learn_candidate_preferences(
        self, user_id: str, candidate: User, feedback: str
    ) -> None:
        """Learn small, bounded tag signals without rewriting the user's profile."""
        signal = FEEDBACK_SIGNAL.get(feedback)
        if signal is None:
            return
        tags = {
            *(f"interest:{item.strip().lower()}" for item in candidate.interests),
            *(f"activity:{item.strip().lower()}" for item in candidate.activities),
        }
        for key in sorted(tag for tag in tags if not tag.endswith(":")):
            self.update_preference(
                user_id=user_id,
                key=key,
                value=key.split(":", 1)[1],
                signal=signal,
            )

    def preference_adjustment(self, user_id: str, candidate: User) -> float:
        candidate_keys = {
            *(f"interest:{item.strip().lower()}" for item in candidate.interests),
            *(f"activity:{item.strip().lower()}" for item in candidate.activities),
        }
        if not candidate_keys:
            return 0.5
        preferences = list(
            self.db.scalars(
                select(Preference).where(
                    Preference.user_id == user_id,
                    Preference.key.in_(candidate_keys),
                )
            )
        )
        if not preferences:
            return 0.5
        average_signal = sum(item.weight for item in preferences) / len(preferences)
        return max(0.25, min(0.75, 0.5 + average_signal))

    def ranking_feedback_adjustments(
        self, user_id: str, candidates: list[User]
    ) -> dict[str, float]:
        direct = self.feedback_adjustments(user_id)
        return {
            candidate.id: max(
                0.25,
                min(
                    0.75,
                    0.7 * direct.get(candidate.id, 0.5)
                    + 0.3 * self.preference_adjustment(user_id, candidate),
                ),
            )
            for candidate in candidates
        }

    def get_recent_candidates(
        self,
        user_id: str,
        limit: int = 200,
        pass_ttl: timedelta = timedelta(hours=24),
    ) -> list[str]:
        """Suppress recent PASS targets and only the immediately previous result page.

        A fixed "last N recommendations" policy slowly exhausts the candidate pool after
        repeated refreshes. This policy rotates only one page while making PASS temporary.
        """
        rows = list(
            self.db.scalars(
                select(Interaction)
                .where(
                    Interaction.actor_id == user_id,
                    Interaction.kind.in_(["PASS", "RECOMMENDED"]),
                    Interaction.target_id.is_not(None),
                )
                .order_by(desc(Interaction.created_at), desc(Interaction.id))
                .limit(limit)
            )
        )
        now = datetime.now(timezone.utc)
        suppressed: dict[str, None] = {}
        latest_session_id: str | None = None
        for item in rows:
            if item.target_id is None:
                continue
            created_at = item.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if item.kind == "PASS" and now - created_at <= pass_ttl:
                suppressed[item.target_id] = None
                continue
            if item.kind != "RECOMMENDED":
                continue
            session_id = item.payload.get("session_id") if item.payload else None
            if latest_session_id is None:
                latest_session_id = session_id or f"interaction:{item.id}"
            current_session_id = session_id or f"interaction:{item.id}"
            if current_session_id == latest_session_id:
                suppressed[item.target_id] = None
        return list(suppressed)

    def get_session(self, session_id: str) -> dict[str, Any]:
        self.db.expire_all()
        record = self.db.get(AgentSessionRecord, session_id)
        if record is None:
            return {}
        if self._is_expired(record.expires_at):
            self.db.delete(record)
            self.db.commit()
            return {}
        return dict(record.state or {})

    def update_session(self, session_id: str, values: dict[str, Any]) -> None:
        """Merge session state using optimistic concurrency and a sliding TTL."""
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_agent_session_update",
                {
                    "p_session_id": session_id,
                    "p_values": values,
                    "p_ttl_seconds": int(self.session_ttl.total_seconds()),
                },
            )
            if result.get("status") == "forbidden":
                raise PermissionError("cannot update another user's agent session")
            if result.get("status") not in {"created", "updated"}:
                raise RuntimeError("agent session update failed")
            return
        self.cleanup_expired_sessions()
        for _attempt in range(5):
            self.db.expire_all()
            record = self.db.get(AgentSessionRecord, session_id)
            now = datetime.now(timezone.utc)
            expires_at = now + self.session_ttl
            if record is not None and self._is_expired(record.expires_at, now):
                self.db.delete(record)
                self.db.commit()
                record = None

            if record is None:
                user_id = values.get("user_id")
                if not isinstance(user_id, str) or not user_id:
                    raise ValueError(
                        "user_id is required when creating an agent session"
                    )
                self.db.add(
                    AgentSessionRecord(
                        id=session_id,
                        user_id=user_id,
                        state=dict(values),
                        version=1,
                        created_at=now,
                        updated_at=now,
                        expires_at=expires_at,
                    )
                )
                try:
                    self.db.commit()
                    return
                except IntegrityError:
                    self.db.rollback()
                    continue

            requested_user_id = values.get("user_id")
            if requested_user_id and requested_user_id != record.user_id:
                raise PermissionError("cannot update another user's agent session")
            merged = dict(record.state or {})
            merged.update(values)
            expected_version = record.version
            result = self.db.execute(
                update(AgentSessionRecord)
                .where(
                    AgentSessionRecord.id == session_id,
                    AgentSessionRecord.version == expected_version,
                )
                .values(
                    state=merged,
                    version=expected_version + 1,
                    updated_at=now,
                    expires_at=expires_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                self.db.commit()
                return
            self.db.rollback()
        raise RuntimeError("agent session update conflicted too many times")

    def cleanup_expired_sessions(self) -> int:
        result = self.db.execute(
            delete(AgentSessionRecord).where(
                AgentSessionRecord.expires_at <= datetime.now(timezone.utc)
            )
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def acquire_session_turn(
        self,
        session_id: str,
        user_id: str,
        turn_id: str,
        lease: timedelta | None = None,
    ) -> None:
        lease = lease or timedelta(seconds=get_settings().agent_turn_lock_seconds)
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_agent_session_acquire",
                {
                    "p_session_id": session_id,
                    "p_user_id": user_id,
                    "p_turn_id": turn_id,
                    "p_lease_seconds": int(lease.total_seconds()),
                },
            )
            status = result.get("status")
            if status == "not_found":
                raise ValueError(f"session not found: {session_id}")
            if status == "forbidden":
                raise PermissionError("cannot continue another user's agent session")
            if status != "acquired":
                raise SessionBusyError("agent session is processing another turn")
            return
        for _attempt in range(5):
            self.db.expire_all()
            record = self.db.get(AgentSessionRecord, session_id)
            if record is None or self._is_expired(record.expires_at):
                raise ValueError(f"session not found: {session_id}")
            if record.user_id != user_id:
                raise PermissionError("cannot continue another user's agent session")
            now = datetime.now(timezone.utc)
            expected_version = record.version
            result = self.db.execute(
                update(AgentSessionRecord)
                .where(
                    AgentSessionRecord.id == session_id,
                    AgentSessionRecord.version == expected_version,
                    or_(
                        AgentSessionRecord.active_turn_id.is_(None),
                        AgentSessionRecord.active_turn_id == turn_id,
                        AgentSessionRecord.lock_expires_at.is_(None),
                        AgentSessionRecord.lock_expires_at <= now,
                    ),
                )
                .values(
                    active_turn_id=turn_id,
                    lock_expires_at=now + lease,
                    version=expected_version + 1,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                self.db.commit()
                return
            self.db.rollback()
            self.db.expire_all()
            current = self.db.get(AgentSessionRecord, session_id)
            if current is not None and current.active_turn_id not in (None, turn_id):
                if current.lock_expires_at is None or not self._is_expired(
                    current.lock_expires_at
                ):
                    raise SessionBusyError("agent session is processing another turn")
        raise SessionBusyError("agent session is processing another turn")

    def release_session_turn(self, session_id: str, turn_id: str) -> None:
        if getattr(self.db, "is_cloudbase_http", False):
            self.db.rpc(
                "campus_agent_session_release",
                {"p_session_id": session_id, "p_turn_id": turn_id},
            )
            return
        now = datetime.now(timezone.utc)
        self.db.execute(
            update(AgentSessionRecord)
            .where(
                AgentSessionRecord.id == session_id,
                AgentSessionRecord.active_turn_id == turn_id,
            )
            .values(
                active_turn_id=None,
                lock_expires_at=None,
                version=AgentSessionRecord.version + 1,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        self.db.commit()

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= now
