from __future__ import annotations

import re

from ..llm.base import LLMProvider
from ..schemas.agent import SocialIntent
from ..schemas.user import PersonalityAnalysis, ProfileParseResult


async def parse_social_intent(message: str, llm: LLMProvider) -> SocialIntent:
    prompt = (
        "提取校园交友需求。activity 可以是用户明确说出的任意活动，"
        "不限于常见示例；只使用用户明确提供的信息，不推断敏感属性。\n"
        f"用户输入：{message}"
    )
    parsed = await llm.structured(prompt, SocialIntent)
    data = parsed.model_dump()
    data["availability"] = normalize_availability(data["availability"])
    study_words = ("自习", "学习", "复习", "备考", "刷题", "考研")
    if any(word in message for word in study_words):
        data["goal"] = "find_study_partner"
        data["activity"] = data["activity"] or "自习"
    campus = data.get("campus")
    if campus and re.search(rf"找.{{0,10}}在{re.escape(campus)}", message):
        data["hard_constraints"] = list(
            dict.fromkeys([*data["hard_constraints"], "campus"])
        )
        data["soft_preferences"] = [
            item for item in data["soft_preferences"] if item != "campus"
        ]
    return SocialIntent.model_validate(data)


def normalize_availability(values: list[str]) -> list[str]:
    normalized = []
    weekdays = "一二三四五六日"
    for raw in values:
        value = raw.strip().replace("星期", "周").replace("礼拜", "周")
        value = value.removeprefix("本") if value.startswith("本周") else value
        if value and value[0] in weekdays:
            value = "周" + value
        value = value.replace("晚间", "晚上")
        if value.endswith("晚"):
            value += "上"
        if value.endswith("早上"):
            value = value[: -len("早上")] + "上午"
        if value and value not in normalized:
            normalized.append(value)
    return normalized


async def parse_profile_text(message: str, llm: LLMProvider) -> ProfileParseResult:
    prompt = f"从以下自述提取可公开校园画像字段：\n{message}"
    parsed = await llm.structured(prompt, ProfileParseResult)
    data = parsed.model_dump()
    data["availability"] = normalize_availability(data["availability"])
    return ProfileParseResult.model_validate(data)


async def analyze_personality_text(
    message: str, llm: LLMProvider
) -> PersonalityAnalysis:
    prompt = (
        "基于用户主动提供的自述，分析仅用于找搭子的非敏感社交风格。"
        "不得推断心理疾病、智力、政治、宗教、性取向、健康、家庭或经济状况；"
        "不得使用 MBTI 等临床或确定性标签。summary 使用温和、非评判中文，"
        "evidence 只能概括用户明确说过的内容。\n"
        f"用户自述：{message}"
    )
    return await llm.structured(prompt, PersonalityAnalysis)
