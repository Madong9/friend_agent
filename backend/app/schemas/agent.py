from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SocialIntent(BaseModel):
    goal: str = "find_partner"
    activity: str | None = Field(default=None, max_length=64)
    availability: list[str] = Field(default_factory=list)
    campus: str | None = None
    level: str | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    session_id: str
    user_id: str
    user_message: str
    goal: str | None = None
    intent: dict[str, Any] = Field(default_factory=dict)
    profile: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    candidate_users: list[dict[str, Any]] = Field(default_factory=list)
    filtered_candidates: list[dict[str, Any]] = Field(default_factory=list)
    ranked_candidates: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    feedback_history: list[dict[str, Any]] = Field(default_factory=list)
    safety_result: dict[str, Any] = Field(default_factory=dict)
    final_response: dict[str, Any] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=3, ge=1, le=20)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)


class AgentResponse(BaseModel):
    goal: str
    intent: dict[str, Any]
    plan: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    suggested_icebreakers: list[str]
    session_id: str
    safety: dict[str, Any]
    response_type: str = "recommendation"
    message: str = ""
    needs_clarification: bool = False
    suggested_replies: list[str] = Field(default_factory=list)
    activities: list[dict[str, Any]] = Field(default_factory=list)
    profile: dict[str, Any] | None = None
