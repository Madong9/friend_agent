from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    body: str = Field(min_length=1, max_length=1000)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: str
    recipient_id: str
    body: str
    safety_result: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class ConversationRead(BaseModel):
    partner: dict[str, Any]
    match_id: int
    unread_count: int
    last_message: MessageRead | None = None
