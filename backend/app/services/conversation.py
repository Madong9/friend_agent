from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.orm import Session

from ..models import Block, Match, Message, User
from ..tools.privacy import public_user


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _pair(user_id: str, partner_id: str) -> tuple[str, str]:
        if user_id == partner_id:
            raise ValueError("cannot chat with self")
        return tuple(sorted((user_id, partner_id)))

    def require_active_match(self, user_id: str, partner_id: str) -> Match:
        user_a, user_b = self._pair(user_id, partner_id)
        if self.db.get(User, partner_id) is None:
            raise ValueError("user not found")
        match = self.db.scalar(
            select(Match).where(
                Match.user_a_id == user_a,
                Match.user_b_id == user_b,
                Match.status == "MATCHED",
            )
        )
        if match is None:
            raise PermissionError("active mutual match required")
        user_a_record = self.db.get(User, user_a)
        user_b_record = self.db.get(User, user_b)
        if (
            user_a_record is not None
            and user_b_record is not None
            and (user_a_record.is_mock or user_b_record.is_mock)
        ):
            raise PermissionError("demo match does not open contact")
        blocked = self.db.scalar(
            select(Block.id).where(
                or_(
                    and_(Block.blocker_id == user_id, Block.blocked_id == partner_id),
                    and_(Block.blocker_id == partner_id, Block.blocked_id == user_id),
                )
            )
        )
        if match is None or blocked is not None:
            raise PermissionError("active mutual match required")
        return match

    @staticmethod
    def _message_pair_condition(user_id: str, partner_id: str):
        return or_(
            and_(Message.sender_id == user_id, Message.recipient_id == partner_id),
            and_(Message.sender_id == partner_id, Message.recipient_id == user_id),
        )

    def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        body: str,
        safety_result: dict,
    ) -> Message:
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_send_message",
                {
                    "p_sender_id": sender_id,
                    "p_recipient_id": recipient_id,
                    "p_body": body,
                    "p_safety_result": safety_result,
                },
            )
            if result.get("status") != "sent":
                raise PermissionError(result.get("status") or "message rejected")
            message = self.db.get(Message, result["message_id"])
            if message is None:
                raise RuntimeError("message transaction returned no row")
            return message
        self.require_active_match(sender_id, recipient_id)
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            body=body,
            safety_result=safety_result,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(
        self,
        user_id: str,
        partner_id: str,
        limit: int = 100,
        before_id: int | None = None,
    ) -> list[Message]:
        self.require_active_match(user_id, partner_id)
        query = select(Message).where(self._message_pair_condition(user_id, partner_id))
        if before_id is not None:
            query = query.where(Message.id < before_id)
        newest_first = list(
            self.db.scalars(
                query.order_by(desc(Message.created_at), desc(Message.id)).limit(limit)
            )
        )
        return list(reversed(newest_first))

    def mark_read(self, user_id: str, partner_id: str) -> int:
        self.require_active_match(user_id, partner_id)
        result = self.db.execute(
            update(Message)
            .where(
                Message.sender_id == partner_id,
                Message.recipient_id == user_id,
                Message.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        self.db.commit()
        return result.rowcount or 0

    def list_conversations(self, user_id: str) -> list[dict]:
        matches = list(
            self.db.scalars(
                select(Match).where(
                    Match.status == "MATCHED",
                    or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
                )
            )
        )
        output = []
        for match in matches:
            partner_id = (
                match.user_b_id if match.user_a_id == user_id else match.user_a_id
            )
            try:
                self.require_active_match(user_id, partner_id)
            except PermissionError:
                continue
            partner = self.db.get(User, partner_id)
            if partner is None:
                continue
            last_message = self.db.scalar(
                select(Message)
                .where(self._message_pair_condition(user_id, partner_id))
                .order_by(desc(Message.created_at), desc(Message.id))
                .limit(1)
            )
            unread_count = self.db.scalar(
                select(func.count())
                .select_from(Message)
                .where(
                    Message.sender_id == partner_id,
                    Message.recipient_id == user_id,
                    Message.read_at.is_(None),
                )
            )
            output.append(
                {
                    "partner": public_user(partner),
                    "match_id": match.id,
                    "unread_count": unread_count or 0,
                    "last_message": last_message,
                }
            )
        return sorted(
            output,
            key=lambda item: (
                item["last_message"].created_at
                if item["last_message"] is not None
                else datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
