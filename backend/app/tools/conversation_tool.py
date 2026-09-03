from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .base import BaseTool


class ConversationToolInput(BaseModel):
    action: Literal["generate_icebreaker", "generate_topics"]
    requester: dict = Field(default_factory=dict)
    candidate: dict = Field(default_factory=dict)
    intent: dict = Field(default_factory=dict)


class ConversationTool(BaseTool):
    name = "ConversationTool"
    description = "Generate icebreakers from public common interests and the current request only."
    input_schema = ConversationToolInput

    async def execute(self, tool_input: ConversationToolInput) -> dict:
        common = sorted(
            set(tool_input.requester.get("interests", []))
            & set(tool_input.candidate.get("interests", []))
        )
        activity = tool_input.intent.get("activity")
        topic = activity or (common[0] if common else "校园活动")
        campus = tool_input.candidate.get("campus", "校内")
        if tool_input.action == "generate_topics":
            topics = common[:3] or [topic]
            return {"topics": topics}
        return {
            "icebreaker": f"看到你也喜欢{topic}，你平时在{campus}一般什么时候参加？最近正想找个搭子。",
            "basis": {
                "common_interests": common,
                "activity": activity,
                "campus": campus,
            },
        }
