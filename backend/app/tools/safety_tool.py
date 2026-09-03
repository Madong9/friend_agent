from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..matching.filters import hard_filter_reason
from ..models import User
from .base import BaseTool


RISK_KEYWORDS = {
    "刷单": "suspected_fraud",
    "贷款": "financial_solicitation",
    "裸照": "sexual_exploitation",
    "私密照片": "privacy_risk",
    "稳赚": "suspected_fraud",
    "返利": "suspected_fraud",
}
SAFE_LINK_HOSTS = {"campus.example", "127.0.0.1", "localhost"}


def _is_allowed_link(url: str) -> bool:
    parsed = urlsplit(url if "://" in url else f"//{url}")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return hostname in SAFE_LINK_HOSTS or hostname.endswith(".campus.example")


class SafetyToolInput(BaseModel):
    action: Literal["check_message", "check_candidate", "check_block"]
    user_id: str | None = None
    candidate_id: str | None = None
    message: str = ""
    intent: dict = Field(default_factory=dict)


class SafetyTool(BaseTool):
    name = "SafetyTool"
    description = "Emit explainable risk signals; it never permanently bans users."
    input_schema = SafetyToolInput

    def __init__(self, db: Session):
        self.db = db

    async def execute(self, tool_input: SafetyToolInput) -> dict:
        if tool_input.action == "check_message":
            signals = sorted(
                {
                    signal
                    for keyword, signal in RISK_KEYWORDS.items()
                    if keyword in tool_input.message
                }
            )
            urls = re.findall(r"(?:https?://|www\.)[^\s<>]+", tool_input.message)
            if any(not _is_allowed_link(url.rstrip(".,，。!?！？")) for url in urls):
                signals = sorted({*signals, "external_link"})
            return {
                "safe": not signals,
                "risk_signals": signals,
                "action": "review" if signals else "allow",
            }

        if not tool_input.user_id or not tool_input.candidate_id:
            raise ValueError("user_id and candidate_id are required")
        user = self.db.get(User, tool_input.user_id)
        candidate = self.db.get(User, tool_input.candidate_id)
        if user is None or candidate is None:
            return {"safe": False, "reason": "user_not_found"}
        reason = hard_filter_reason(self.db, user, candidate, tool_input.intent)
        if tool_input.action == "check_block":
            safe = reason != "blocked_relation"
        else:
            safe = reason is None
        return {"safe": safe, "reason": reason}
