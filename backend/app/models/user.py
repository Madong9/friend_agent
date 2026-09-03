from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    school_email: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True
    )
    wechat_openid: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    school_uid: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    school_display_name: Mapped[str | None] = mapped_column(String(128))
    identity_provider: Mapped[str] = mapped_column(String(32), default="email")
    school: Mapped[str] = mapped_column(
        String(128), nullable=False, default="中国科学技术大学"
    )
    campus: Mapped[str] = mapped_column(String(64), nullable=False)
    grade: Mapped[str] = mapped_column(String(32), nullable=False)
    major: Mapped[str] = mapped_column(String(128), nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="")
    social_goals: Mapped[list[str]] = mapped_column(JSON, default=list)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    activities: Mapped[list[str]] = mapped_column(JSON, default=list)
    availability: Mapped[list[str]] = mapped_column(JSON, default=list)
    social_style: Mapped[str] = mapped_column(String(64), default="随和")
    avoidances: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommendation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    campus_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    personality_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    personality_traits: Mapped[dict] = mapped_column(JSON, default=dict)
    personality_summary: Mapped[str] = mapped_column(Text, default="")
    personality_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    last_token_revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=utcnow
    )
