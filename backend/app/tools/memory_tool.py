from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..memory import MemoryManager
from .base import BaseTool


class MemoryToolInput(BaseModel):
    action: Literal["load_memory", "update_memory", "record_recommendation"]
    user_id: str
    session_id: str = ""
    candidate_ids: list[str] = Field(default_factory=list)
    values: dict = Field(default_factory=dict)


class MemoryTool(BaseTool):
    name = "MemoryTool"
    description = (
        "Read persistent user memory and update session/recommendation memory."
    )
    input_schema = MemoryToolInput

    def __init__(self, db: Session):
        self.manager = MemoryManager(db)

    async def execute(self, tool_input: MemoryToolInput) -> dict:
        if tool_input.action == "load_memory":
            return self.manager.load_user_memory(tool_input.user_id)
        if tool_input.action == "record_recommendation":
            self.manager.record_recommendation(
                tool_input.user_id, tool_input.candidate_ids, tool_input.session_id
            )
            return {"recorded": len(tool_input.candidate_ids)}
        self.manager.update_session(
            tool_input.session_id,
            {**tool_input.values, "user_id": tool_input.user_id},
        )
        return self.manager.get_session(tool_input.session_id)
