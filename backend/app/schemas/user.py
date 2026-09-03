from __future__ import annotations

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nickname: str = Field(min_length=1, max_length=64)
    school: str = Field(default="中国科学技术大学", min_length=1, max_length=128)
    campus: str = Field(min_length=1, max_length=64)
    grade: str = Field(min_length=1, max_length=32)
    major: str = Field(min_length=1, max_length=128)
    bio: str = Field(default="", max_length=1000)
    social_goals: list[str] = Field(default_factory=list, max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=30)
    activities: list[str] = Field(default_factory=list, max_length=30)
    availability: list[str] = Field(default_factory=list, max_length=30)
    social_style: str = Field(default="随和", max_length=64)
    avoidances: list[str] = Field(default_factory=list, max_length=30)
    recommendation_enabled: bool = True


class UserCreate(UserBase):
    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    school_email: str = Field(min_length=6, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    school: str | None = Field(default=None, min_length=1, max_length=128)
    campus: str | None = Field(default=None, min_length=1, max_length=64)
    grade: str | None = Field(default=None, min_length=1, max_length=32)
    major: str | None = Field(default=None, min_length=1, max_length=128)
    bio: str | None = Field(default=None, max_length=1000)
    social_goals: list[str] | None = Field(default=None, max_length=20)
    interests: list[str] | None = Field(default=None, max_length=30)
    activities: list[str] | None = Field(default=None, max_length=30)
    availability: list[str] | None = Field(default=None, max_length=30)
    social_style: str | None = Field(default=None, max_length=64)
    avoidances: list[str] | None = Field(default=None, max_length=30)
    recommendation_enabled: bool | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_mock: bool = False
    campus_verified: bool = False
    personality_consent: bool = False
    personality_traits: dict[str, str] = Field(default_factory=dict)
    personality_summary: str = ""
    personality_updated_at: datetime | None = None
    created_at: datetime


class ProfileParseResult(BaseModel):
    grade: str | None = None
    interests: list[str] = Field(default_factory=list)
    social_style: str | None = None
    availability: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)


class PersonalityTraits(BaseModel):
    energy: Literal["quiet", "balanced", "outgoing"] = "balanced"
    planning: Literal["spontaneous", "balanced", "planned"] = "balanced"
    communication: Literal["reserved", "balanced", "expressive"] = "balanced"
    group_preference: Literal["one_on_one", "small_group", "group"] = "small_group"
    connection_pace: Literal["slow_warmup", "balanced", "quick_connect"] = "balanced"


class PersonalityAnalysis(BaseModel):
    traits: PersonalityTraits
    summary: str = Field(min_length=1, max_length=300)
    evidence: list[str] = Field(default_factory=list, max_length=5)


class PersonalityAnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=10, max_length=2000)
    consent: bool
