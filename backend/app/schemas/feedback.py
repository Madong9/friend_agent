from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FeedbackType(str, Enum):
    LIKE = "LIKE"
    PASS = "PASS"
    INTERESTED = "INTERESTED"
    MATCHED = "MATCHED"
    CHATTED = "CHATTED"
    MET = "MET"
    NOT_RELEVANT = "NOT_RELEVANT"
    BLOCK = "BLOCK"
    REPORT = "REPORT"


class FeedbackCreate(BaseModel):
    model_config = {"extra": "forbid"}

    candidate_id: str
    feedback: FeedbackType

    @field_validator("feedback")
    @classmethod
    def reject_server_owned_events(cls, value: FeedbackType) -> FeedbackType:
        if value in {FeedbackType.MATCHED, FeedbackType.BLOCK, FeedbackType.REPORT}:
            raise ValueError(
                "server-owned match/safety events must use the dedicated endpoint"
            )
        return value


class BlockCreate(BaseModel):
    model_config = {"extra": "forbid"}

    blocked_user_id: str


class ReportCreate(BaseModel):
    model_config = {"extra": "forbid"}

    reported_user_id: str
    category: Literal[
        "HARASSMENT",
        "FRAUD",
        "FAKE_IDENTITY",
        "INAPPROPRIATE_CONTENT",
        "OTHER",
    ] = "OTHER"
    reason: str = Field(min_length=2, max_length=1000)
