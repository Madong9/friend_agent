from __future__ import annotations

import re

from pydantic import BaseModel

from ..schemas.agent import SocialIntent
from ..schemas.user import PersonalityAnalysis, PersonalityTraits, ProfileParseResult
from .base import LLMProvider, T


class MockLLMProvider(LLMProvider):
    """Deterministic Chinese parser for local demos and repeatable tests."""

    provider_label = "mock"

    async def structured(self, prompt: str, output_schema: type[T]) -> T:
        if output_schema is SocialIntent:
            return self._intent(prompt)  # type: ignore[return-value]
        if output_schema is ProfileParseResult:
            return self._profile(prompt)  # type: ignore[return-value]
        if output_schema is PersonalityAnalysis:
            return self._personality(prompt)  # type: ignore[return-value]
        if issubclass(output_schema, BaseModel):
            return output_schema.model_validate({})
        raise TypeError(f"unsupported schema: {output_schema}")

    def _profile(self, text: str) -> ProfileParseResult:
        grade_match = re.search(r"(大[一二三四五]|研[一二三]|博士?[一二三四]?)", text)
        known_interests = [
            "羽毛球",
            "跑步",
            "摄影",
            "篮球",
            "阅读",
            "电影",
            "音乐",
            "桌游",
            "编程",
            "英语",
        ]
        interests = [tag for tag in known_interests if tag in text]
        styles = [style for style in ["慢热", "外向", "安静", "随和"] if style in text]
        times = []
        for phrase in [
            "周六下午",
            "周日下午",
            "周末下午",
            "周末上午",
            "工作日晚上",
            "晚上",
            "白天",
        ]:
            if phrase in text and not any(phrase in existing for existing in times):
                times.append(phrase)
        return ProfileParseResult(
            grade=grade_match.group(1) if grade_match else None,
            interests=interests,
            activities=interests.copy(),
            social_style=styles[0] if styles else None,
            availability=times,
        )

    def _intent(self, text: str) -> SocialIntent:
        study_words = ["自习", "学习", "复习", "备考", "刷题", "考研"]
        activity = next(
            (
                tag
                for tag in [
                    "羽毛球",
                    "跑步",
                    "摄影",
                    "篮球",
                    "桌游",
                    "自习",
                    "英语角",
                    "阅读",
                ]
                if tag in text
            ),
            None,
        )
        if activity is None and any(word in text for word in study_words):
            activity = "自习"
        availability = [
            phrase
            for phrase in [
                "周六下午",
                "周日下午",
                "周末下午",
                "周末上午",
                "工作日晚上",
                "晚上",
            ]
            if phrase in text
        ]
        campus = next(
            (value for value in ["西区", "东区", "北区"] if value in text), None
        )
        level = next(
            (value for value in ["休闲", "入门", "中级", "竞技"] if value in text), None
        )
        if any(word in text for word in study_words):
            goal = "find_study_partner"
        elif activity:
            goal = "find_activity_partner"
        else:
            goal = "find_interest_friend"
        hard_constraints = []
        soft_preferences = []
        if campus:
            campus_is_required = any(
                word in text for word in ["必须", "只限", "限定", "只能"]
            ) or bool(re.search(rf"找.{{0,10}}在{re.escape(campus)}", text))
            if campus_is_required:
                hard_constraints.append("campus")
            else:
                soft_preferences.append("campus")
        if level:
            soft_preferences.append("level")
        return SocialIntent(
            goal=goal,
            activity=activity,
            availability=availability,
            campus=campus,
            level=level,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
        )

    def _personality(self, text: str) -> PersonalityAnalysis:
        quiet = any(word in text for word in ("慢热", "安静", "内向"))
        outgoing = any(word in text for word in ("外向", "健谈", "主动"))
        planned = any(word in text for word in ("计划", "提前", "准时"))
        spontaneous = any(word in text for word in ("随性", "临时", "说走就走"))
        one_on_one = any(word in text for word in ("一对一", "两个人", "小范围"))
        group = any(word in text for word in ("热闹", "多人", "一群人"))
        traits = PersonalityTraits(
            energy="quiet" if quiet else "outgoing" if outgoing else "balanced",
            planning="planned"
            if planned
            else "spontaneous"
            if spontaneous
            else "balanced",
            communication="reserved"
            if quiet
            else "expressive"
            if outgoing
            else "balanced",
            group_preference="one_on_one"
            if one_on_one
            else "group"
            if group
            else "small_group",
            connection_pace="slow_warmup"
            if quiet
            else "quick_connect"
            if outgoing
            else "balanced",
        )
        return PersonalityAnalysis(
            traits=traits,
            summary="根据你的自述，你更适合节奏和交流方式相近的搭子。",
            evidence=["仅依据本次主动填写的社交偏好"],
        )
