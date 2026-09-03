from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PartnerRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    intent: dict[str, Any]
    normalized_activity: str | None
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class PartnerRequestStatusUpdate(BaseModel):
    status: Literal["OPEN", "PAUSED", "EXPIRED"]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    body: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime
