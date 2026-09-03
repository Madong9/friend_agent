from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import User
from .base import BaseTool
from .privacy import public_user


class ProfileToolInput(BaseModel):
    action: Literal["load_profile", "update_profile"]
    user_id: str
    updates: dict[str, Any] = Field(default_factory=dict)


class ProfileTool(BaseTool):
    name = "ProfileTool"
    description = "Load or update the requesting user's explicitly provided profile."
    input_schema = ProfileToolInput
    ALLOWED_UPDATES = {
        "nickname",
        "campus",
        "grade",
        "major",
        "bio",
        "social_goals",
        "interests",
        "activities",
        "availability",
        "social_style",
        "avoidances",
        "recommendation_enabled",
    }

    def __init__(self, db: Session):
        self.db = db

    async def execute(self, tool_input: ProfileToolInput) -> dict:
        user = self.db.get(User, tool_input.user_id)
        if user is None:
            raise ValueError(f"user not found: {tool_input.user_id}")
        if tool_input.action == "update_profile":
            unknown = set(tool_input.updates) - self.ALLOWED_UPDATES
            if unknown:
                raise ValueError(f"fields cannot be updated: {sorted(unknown)}")
            for key, value in tool_input.updates.items():
                setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
        return public_user(user)
