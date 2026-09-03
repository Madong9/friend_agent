from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..matching.similarity import normalize_tag
from ..models import Notification, PartnerRequest


class PartnerLoopService:
    """Persist active partner demand and notify earlier compatible requesters."""

    def __init__(self, db: Session):
        self.db = db

    def record_request(
        self,
        user_id: str,
        session_id: str,
        intent: dict,
        candidate_ids: list[str],
    ) -> PartnerRequest:
        now = datetime.now(timezone.utc)
        activity = intent.get("activity")
        normalized_activity = normalize_tag(activity) if activity else None
        item = self.db.scalar(
            select(PartnerRequest).where(PartnerRequest.session_id == session_id)
        )
        if item is None:
            item = PartnerRequest(
                user_id=user_id,
                session_id=session_id,
                intent=dict(intent),
                normalized_activity=normalized_activity,
                status="FULFILLED" if candidate_ids else "OPEN",
                expires_at=now + timedelta(days=14),
                created_at=now,
                updated_at=now,
            )
            self.db.add(item)
        else:
            if item.user_id != user_id:
                raise PermissionError("cannot update another user's partner request")
            item.intent = dict(intent)
            item.normalized_activity = normalized_activity
            item.status = "FULFILLED" if candidate_ids else "OPEN"
            item.expires_at = now + timedelta(days=14)
            item.updated_at = now
        self.db.commit()
        self.db.refresh(item)
        if candidate_ids and normalized_activity:
            self._notify_waiting_users(
                requester_id=user_id,
                session_id=session_id,
                normalized_activity=normalized_activity,
                candidate_ids=set(candidate_ids),
            )
        return item

    def _notify_waiting_users(
        self,
        *,
        requester_id: str,
        session_id: str,
        normalized_activity: str,
        candidate_ids: set[str],
    ) -> None:
        now = datetime.now(timezone.utc)
        waiting = list(
            self.db.scalars(
                select(PartnerRequest).where(
                    PartnerRequest.status == "OPEN",
                    PartnerRequest.normalized_activity == normalized_activity,
                    PartnerRequest.user_id != requester_id,
                    PartnerRequest.expires_at > now,
                )
            )
        )
        for request in waiting:
            if request.user_id not in candidate_ids:
                continue
            existing = list(
                self.db.scalars(
                    select(Notification).where(
                        Notification.user_id == request.user_id,
                        Notification.kind == "NEW_PARTNER_CANDIDATE",
                    )
                )
            )
            if any(
                notice.payload.get("source_session_id") == session_id
                for notice in existing
            ):
                continue
            self.db.add(
                Notification(
                    user_id=request.user_id,
                    kind="NEW_PARTNER_CANDIDATE",
                    title="发现新的搭子候选",
                    body=f"有同学也在寻找{normalized_activity}搭子，回来看看吧。",
                    payload={
                        "activity": normalized_activity,
                        "source_session_id": session_id,
                        "request_id": request.id,
                    },
                )
            )
        self.db.commit()

    def list_requests(self, user_id: str) -> list[PartnerRequest]:
        now = datetime.now(timezone.utc)
        items = list(
            self.db.scalars(
                select(PartnerRequest)
                .where(PartnerRequest.user_id == user_id)
                .order_by(desc(PartnerRequest.updated_at))
            )
        )
        changed = False
        for item in items:
            comparable_now = now if item.expires_at.tzinfo else now.replace(tzinfo=None)
            if item.status == "OPEN" and item.expires_at <= comparable_now:
                item.status = "EXPIRED"
                item.updated_at = now
                changed = True
        if changed:
            self.db.commit()
        return items

    def set_request_status(
        self, user_id: str, request_id: int, status: str
    ) -> PartnerRequest:
        item = self.db.get(PartnerRequest, request_id)
        if item is None:
            raise ValueError("partner request not found")
        if item.user_id != user_id:
            raise PermissionError("cannot update another user's partner request")
        item.status = status
        now = datetime.now(timezone.utc)
        item.updated_at = now
        comparable_now = now if item.expires_at.tzinfo else now.replace(tzinfo=None)
        if status == "OPEN" and item.expires_at <= comparable_now:
            item.expires_at = now + timedelta(days=14)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_notifications(
        self, user_id: str, unread_only: bool = False
    ) -> list[Notification]:
        statement = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            statement = statement.where(Notification.read_at.is_(None))
        return list(
            self.db.scalars(
                statement.order_by(desc(Notification.created_at), desc(Notification.id))
            )
        )

    def mark_notification_read(self, user_id: str, notification_id: int) -> Notification:
        item = self.db.get(Notification, notification_id)
        if item is None:
            raise ValueError("notification not found")
        if item.user_id != user_id:
            raise PermissionError("cannot read another user's notification")
        item.read_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(item)
        return item
