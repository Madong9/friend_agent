from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AgentTask(str, Enum):
    FIND_PARTNER = "find_partner"
    FIND_ACTIVITY = "find_activity"
    UPDATE_PROFILE = "update_profile"
    EXPLAIN_RECOMMENDATION = "explain_recommendation"
    CONTINUE_CLARIFICATION = "continue_clarification"
    CONFIRM_RELAXATION = "confirm_relaxation"


@dataclass(frozen=True)
class RouteDecision:
    task: AgentTask
    reason: str


class TaskRouter:
    """Route only among product-approved tasks; tools remain program-controlled."""

    AFFIRMATIVE_EXACT = {"是", "是的", "可以", "好", "好的", "行", "同意", "没问题"}
    AFFIRMATIVE_PHRASES = ("可以", "同意", "放宽", "没问题", "试试")
    NEGATIVE_PHRASES = (
        "不是",
        "不可以",
        "不同意",
        "不放宽",
        "不行",
        "不好",
        "不要",
        "不用",
        "取消",
        "拒绝",
        "否",
    )
    PERSON_WORDS = ("搭子", "朋友", "伙伴", "同学", "找人", "一起的人")
    ACTIVITY_WORDS = ("有什么活动", "有哪些活动", "查活动", "推荐活动", "校园活动")
    EXPLAIN_WORDS = ("为什么推荐", "推荐理由", "解释推荐", "为什么是")
    PROFILE_WORDS = ("更新画像", "修改资料", "更新资料", "记住我", "我的资料")

    @classmethod
    def _is_affirmative(cls, message: str) -> bool:
        normalized = message.strip().strip("，。！？!?、 ")
        if not normalized or any(word in normalized for word in cls.NEGATIVE_PHRASES):
            return False
        return normalized in cls.AFFIRMATIVE_EXACT or any(
            phrase in normalized for phrase in cls.AFFIRMATIVE_PHRASES
        )

    def route(self, message: str, session: dict[str, Any]) -> RouteDecision:
        if session.get("pending_relaxation") and self._is_affirmative(message):
            return RouteDecision(
                AgentTask.CONFIRM_RELAXATION, "user_confirmed_constraint_relaxation"
            )
        if session.get("pending_slot"):
            return RouteDecision(
                AgentTask.CONTINUE_CLARIFICATION, "answering_pending_question"
            )
        if any(word in message for word in self.EXPLAIN_WORDS):
            return RouteDecision(
                AgentTask.EXPLAIN_RECOMMENDATION, "explicit_explanation_request"
            )
        if any(word in message for word in self.ACTIVITY_WORDS) and not any(
            word in message for word in self.PERSON_WORDS
        ):
            return RouteDecision(AgentTask.FIND_ACTIVITY, "explicit_activity_search")
        if any(word in message for word in self.PROFILE_WORDS):
            return RouteDecision(AgentTask.UPDATE_PROFILE, "explicit_profile_update")
        return RouteDecision(AgentTask.FIND_PARTNER, "default_social_matching_task")
