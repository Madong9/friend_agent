from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import get_settings
from ..llm import LLMProvider, create_llm_provider
from ..matching.similarity import normalize_tag
from ..schemas.agent import AgentResponse, SocialIntent
from ..services.parsers import parse_profile_text, parse_social_intent
from ..services.partner_loop import PartnerLoopService
from ..tools.activity_tool import ActivityTool, ActivityToolInput
from ..tools.conversation_tool import ConversationTool, ConversationToolInput
from ..tools.matching_tool import MatchingTool, MatchingToolInput
from ..tools.memory_tool import MemoryTool, MemoryToolInput
from ..tools.profile_tool import ProfileTool, ProfileToolInput
from ..tools.safety_tool import SafetyTool, SafetyToolInput
from .planner import Planner
from .router import AgentTask, TaskRouter
from .state import AgentState
from .trace import AgentTrace, TraceStore


class CampusSocialAgent:
    """A bounded campus-social agent with routing, replanning, memory and trace."""

    def __init__(
        self,
        db: Session,
        llm: LLMProvider | None = None,
        trace_enabled: bool | None = None,
    ):
        self.db = db
        self.llm = llm or create_llm_provider()
        self.profile_tool = ProfileTool(db)
        self.memory_tool = MemoryTool(db)
        self.matching_tool = MatchingTool(db)
        self.activity_tool = ActivityTool(db)
        self.safety_tool = SafetyTool(db)
        self.conversation_tool = ConversationTool()
        self.trace_store = TraceStore(db)
        self.planner = Planner()
        self.router = TaskRouter()
        self.trace_enabled = (
            get_settings().debug_agent_trace if trace_enabled is None else trace_enabled
        )

    async def _check_safety(
        self, user_id: str, message: str, ranked: list[dict], intent: dict
    ) -> dict:
        message_result = await self.safety_tool.execute(
            SafetyToolInput(action="check_message", user_id=user_id, message=message)
        )
        safe_candidate_ids: list[str] = []
        candidate_risks: dict[str, str] = {}
        for candidate in ranked:
            result = await self.safety_tool.execute(
                SafetyToolInput(
                    action="check_candidate",
                    user_id=user_id,
                    candidate_id=candidate["id"],
                    intent=intent,
                )
            )
            if result["safe"]:
                safe_candidate_ids.append(candidate["id"])
            else:
                candidate_risks[candidate["id"]] = (
                    result.get("reason") or "safety_check_failed"
                )
        return {
            **message_result,
            "candidates_checked": len(ranked),
            "safe_candidate_ids": safe_candidate_ids,
            "candidate_risks": candidate_risks,
        }

    async def _message_safety(self, user_id: str, message: str) -> dict:
        return await self.safety_tool.execute(
            SafetyToolInput(action="check_message", user_id=user_id, message=message)
        )

    async def _remember_explicit_activity(
        self, state: AgentState, intent: SocialIntent
    ) -> bool:
        """Persist an explicitly requested activity as a deduplicated profile tag."""
        activity = (intent.activity or "").strip()
        if not activity or len(activity) > 64:
            return False
        compact_message = "".join(state.user_message.casefold().split())
        compact_activity = "".join(activity.casefold().split())
        if compact_activity not in compact_message:
            return False
        current = list(state.profile.get("activities") or [])
        if normalize_tag(activity) in {normalize_tag(item) for item in current}:
            return False
        if len(current) >= 30:
            return False
        safety = await self._message_safety(state.user_id, state.user_message)
        if not safety["safe"]:
            return False
        profile_input = ProfileToolInput(
            action="update_profile",
            user_id=state.user_id,
            updates={"activities": [*current, activity]},
        )
        state.profile = await self.profile_tool.execute(profile_input)
        state.tool_calls.append(
            {"tool": self.profile_tool.name, "action": "remember_activity"}
        )
        return True

    @staticmethod
    def _merge_intent(base: dict[str, Any], parsed: SocialIntent) -> SocialIntent:
        merged = SocialIntent.model_validate(base).model_dump()
        incoming = parsed.model_dump()
        for field in ("activity", "campus", "level"):
            if incoming[field]:
                merged[field] = incoming[field]
        if incoming["availability"]:
            merged["availability"] = incoming["availability"]
        if incoming["activity"] or not merged.get("goal"):
            merged["goal"] = incoming["goal"]
        for field in ("hard_constraints", "soft_preferences"):
            merged[field] = list(dict.fromkeys([*merged[field], *incoming[field]]))
        return SocialIntent.model_validate(merged)

    @staticmethod
    def _missing_slot(
        intent: SocialIntent, relaxed_slots: list[str], profile: dict[str, Any]
    ) -> str | None:
        if not intent.activity and "activity" not in relaxed_slots:
            return "activity"
        can_use_profile_time = intent.goal == "find_study_partner" and bool(
            profile.get("availability")
        )
        if (
            not intent.availability
            and "availability" not in relaxed_slots
            and not can_use_profile_time
        ):
            return "availability"
        return None

    @staticmethod
    def _question_for(slot: str) -> str:
        if slot == "activity":
            return "你更想找哪一类搭子？例如羽毛球、自习、跑步或桌游。"
        return "你通常什么时间方便？例如周六下午、周末上午或工作日晚上。"

    @staticmethod
    def _response(
        state: AgentState,
        *,
        response_type: str,
        message: str,
        matches: list[dict] | None = None,
        icebreakers: list[str] | None = None,
        safety: dict | None = None,
        needs_clarification: bool = False,
        suggested_replies: list[str] | None = None,
        activities: list[dict] | None = None,
        profile: dict | None = None,
    ) -> dict:
        return AgentResponse(
            goal=state.goal or "find_partner",
            intent=state.intent,
            plan=state.plan,
            matches=matches or [],
            suggested_icebreakers=icebreakers or [],
            session_id=state.session_id,
            safety=safety or {},
            response_type=response_type,
            message=message,
            needs_clarification=needs_clarification,
            suggested_replies=suggested_replies or [],
            activities=activities or [],
            profile=profile,
        ).model_dump()

    def _load_session(
        self, user_id: str, requested_session_id: str | None
    ) -> tuple[str, dict]:
        if requested_session_id is None:
            return str(uuid4()), {}
        session = self.memory_tool.manager.get_session(requested_session_id)
        if not session:
            raise ValueError(f"session not found: {requested_session_id}")
        if session.get("user_id") != user_id:
            raise PermissionError("cannot continue another user's agent session")
        return requested_session_id, session

    def _new_trace(self, session_id: str, user_id: str) -> tuple[AgentTrace, int]:
        existing = self.trace_store.get(session_id) if self.trace_enabled else None
        if existing is not None and existing.user_id == user_id:
            return existing, len(existing.entries)
        return AgentTrace(session_id=session_id, user_id=user_id), 0

    @property
    def _llm_name(self) -> str:
        return getattr(self.llm, "provider_label", "LLM")

    async def _capture_llm(
        self,
        trace: AgentTrace,
        step: int,
        action: str,
        tool_input: dict[str, Any],
        operation,
    ):
        """Capture an LLM step and record the provider that actually answered.

        A resilient provider only knows whether it used its fallback after the
        request completes, so the trace label must be updated after execution.
        """

        result = await trace.capture(
            step, action, self._llm_name, tool_input, operation
        )
        provider = self._llm_name
        trace.entries[-1].tool = provider
        trace.entries[-1].metadata["provider"] = provider
        return result

    def _has_active_match(self, user_id: str, candidate_id: str) -> bool:
        from sqlalchemy import select

        from ..models import Match

        user_a, user_b = sorted((user_id, candidate_id))
        return (
            self.db.scalar(
                select(Match.id).where(
                    Match.user_a_id == user_a,
                    Match.user_b_id == user_b,
                    Match.status == "MATCHED",
                )
            )
            is not None
        )

    async def run(
        self,
        user_id: str,
        message: str,
        limit: int = 3,
        session_id: str | None = None,
    ) -> dict:
        session_id, session = self._load_session(user_id, session_id)
        if not session:
            self.memory_tool.manager.update_session(
                session_id, {"user_id": user_id, "turn_count": 0}
            )
        turn_id = str(uuid4())
        self.memory_tool.manager.acquire_session_turn(session_id, user_id, turn_id)
        trace: AgentTrace | None = None
        try:
            session = self.memory_tool.manager.get_session(session_id)
            self.memory_tool.manager.update_session(
                session_id,
                {
                    "user_id": user_id,
                    "turn_count": int(session.get("turn_count", 0)) + 1,
                },
            )
            session = self.memory_tool.manager.get_session(session_id)
            decision = self.router.route(message, session)
            state = AgentState(
                session_id=session_id, user_id=user_id, user_message=message
            )
            state.plan = self.planner.create_plan(state, decision.task)
            trace, step_base = self._new_trace(session_id, user_id)

            def step(local_step: int) -> int:
                return step_base + local_step

            if decision.task == AgentTask.FIND_ACTIVITY:
                response = await self._run_activity(state, trace, step)
            elif decision.task == AgentTask.UPDATE_PROFILE:
                response = await self._run_profile_update(state, trace, step)
            elif decision.task == AgentTask.EXPLAIN_RECOMMENDATION:
                response = await self._run_explanation(state, trace, step, session)
            else:
                response = await self._run_matching(
                    state, trace, step, decision.task, session, limit
                )
            state.final_response = response
            return response
        finally:
            try:
                if self.trace_enabled and trace is not None:
                    self.trace_store.save(trace)
            finally:
                self.memory_tool.manager.release_session_turn(session_id, turn_id)

    async def _run_matching(
        self,
        state: AgentState,
        trace: AgentTrace,
        step,
        task: AgentTask,
        session: dict,
        limit: int,
    ) -> dict:
        user_id = state.user_id
        message = state.user_message
        profile_input = ProfileToolInput(action="load_profile", user_id=user_id)
        state.profile = await trace.capture(
            step(1),
            "load_profile",
            self.profile_tool.name,
            profile_input.model_dump(),
            lambda: self.profile_tool.execute(profile_input),
        )

        memory_input = MemoryToolInput(action="load_memory", user_id=user_id)
        memory = await trace.capture(
            step(2),
            "load_memory",
            self.memory_tool.name,
            {"user_id": user_id},
            lambda: self.memory_tool.execute(memory_input),
        )
        state.preferences = memory["preferences"]
        state.feedback_history = memory["interactions"]

        async def resolve_intent() -> SocialIntent:
            if task == AgentTask.CONFIRM_RELAXATION:
                intent = SocialIntent.model_validate(session["intent"])
                field = session["pending_relaxation"]
                data = intent.model_dump()
                if field == "campus":
                    data["hard_constraints"] = [
                        item for item in data["hard_constraints"] if item != "campus"
                    ]
                    data["soft_preferences"] = list(
                        dict.fromkeys([*data["soft_preferences"], "campus"])
                    )
                return SocialIntent.model_validate(data)
            parsed = await parse_social_intent(message, self.llm)
            if task == AgentTask.CONTINUE_CLARIFICATION:
                return self._merge_intent(session["intent"], parsed)
            return parsed

        intent_action = {
            AgentTask.CONTINUE_CLARIFICATION: "merge_clarification",
            AgentTask.CONFIRM_RELAXATION: "apply_constraint_relaxation",
        }.get(task, "parse_intent")
        intent_model = await self._capture_llm(
            trace,
            step(3),
            intent_action,
            {"message_length": len(message)},
            resolve_intent,
        )
        if task == AgentTask.CONFIRM_RELAXATION:
            trace.entries[-1].tool = "Agent"
            trace.entries[-1].metadata = {}
        state.intent = intent_model.model_dump()
        state.goal = intent_model.goal
        state.hard_constraints = intent_model.hard_constraints
        state.soft_preferences = intent_model.soft_preferences
        activity_added = await self._remember_explicit_activity(state, intent_model)
        if activity_added:
            trace.entries[-1].metadata["activity_preference_added"] = (
                intent_model.activity
            )

        relaxed_slots = list(session.get("relaxed_slots", []))
        if task == AgentTask.CONFIRM_RELAXATION:
            relaxed_field = session["pending_relaxation"]
            relaxed_slots = list(dict.fromkeys([*relaxed_slots, relaxed_field]))
        missing_slot = self._missing_slot(intent_model, relaxed_slots, state.profile)
        if missing_slot and task != AgentTask.CONFIRM_RELAXATION:
            state.plan = self.planner.replan_for_clarification(state)
            question = self._question_for(missing_slot)
            trace.add_observation(
                step(4), "ask_clarification", "Agent", {"missing_slot": missing_slot}
            )
            self.memory_tool.manager.update_session(
                state.session_id,
                {
                    "user_id": user_id,
                    "intent": state.intent,
                    "pending_slot": missing_slot,
                    "pending_relaxation": None,
                    "relaxed_slots": relaxed_slots,
                },
            )
            return self._response(
                state,
                response_type="clarification",
                message=question,
                needs_clarification=True,
                suggested_replies=(
                    ["羽毛球", "跑步", "自习", "桌游"]
                    if missing_slot == "activity"
                    else ["周六下午", "周末上午", "工作日晚上"]
                ),
            )

        search_intent = dict(state.intent)
        if "availability" in relaxed_slots:
            search_intent["availability"] = []
        search_input = MatchingToolInput(
            action="search_candidates", user_id=user_id, intent=search_intent, limit=100
        )
        search = await trace.capture(
            step(4),
            "search_candidates",
            self.matching_tool.name,
            {"user_id": user_id, "intent": search_intent},
            lambda: self.matching_tool.execute(search_input),
        )
        activity_mismatch = False
        if intent_model.activity and "activity" not in relaxed_slots:
            desired_activity = normalize_tag(intent_model.activity)
            exact_candidates = [
                candidate
                for candidate in search["candidates"]
                if desired_activity
                in {normalize_tag(item) for item in candidate.get("activities", [])}
            ]
            if exact_candidates:
                exact_ids = {candidate["id"] for candidate in exact_candidates}
                search["candidate_ids"] = [
                    candidate_id
                    for candidate_id in search["candidate_ids"]
                    if candidate_id in exact_ids
                ]
                search["candidates"] = exact_candidates
                search["filtered_count"] = len(exact_candidates)
            elif search["candidate_ids"]:
                activity_mismatch = True
                for candidate_id in search["candidate_ids"]:
                    search["filter_reasons"][candidate_id] = "activity_mismatch"
                search["candidate_ids"] = []
                search["candidates"] = []
                search["filtered_count"] = 0
        state.candidate_users = search["candidates"]
        state.tool_calls.append(
            {"tool": self.matching_tool.name, "action": "search_candidates"}
        )
        trace.add_observation(
            step(5),
            "hard_filter",
            self.matching_tool.name,
            {
                "filtered_count": search["filtered_count"],
                "filter_reasons": search["filter_reasons"],
            },
        )
        state.filtered_candidates = search["candidates"]

        if not search["candidate_ids"]:
            state.plan = self.planner.replan_for_no_candidates(state)
            relaxation = (
                "activity"
                if activity_mismatch
                else "campus"
                if "campus" in intent_model.hard_constraints
                and "campus" not in relaxed_slots
                else "availability"
                if intent_model.availability
                and "availability" not in relaxed_slots
                else None
            )
            trace.add_observation(
                step(6),
                "observe_no_candidates",
                self.matching_tool.name,
                {"filter_reasons": search["filter_reasons"]},
            )
            trace.add_observation(
                step(7),
                "request_constraint_relaxation",
                "Agent",
                {"constraint": relaxation},
            )
            if relaxation == "campus":
                reply = (
                    "当前严格校区条件下没有合适人选。是否同意把校区从硬条件改为偏好？"
                )
            elif relaxation == "availability":
                reply = "当前时间条件下没有合适人选。是否同意放宽可用时间后再找一次？"
            elif relaxation == "activity":
                reply = (
                    f"暂时没有同样想参加{intent_model.activity}的搭子。"
                    "是否同意推荐活动偏好相近的同学？"
                )
            else:
                reply = "当前没有合适人选。你可以补充或调整活动、时间、校区条件。"
            PartnerLoopService(self.db).record_request(
                user_id, state.session_id, state.intent, []
            )
            self.memory_tool.manager.update_session(
                state.session_id,
                {
                    "user_id": user_id,
                    "intent": state.intent,
                    "pending_slot": None,
                    "pending_relaxation": relaxation,
                    "relaxed_slots": relaxed_slots,
                },
            )
            return self._response(
                state,
                response_type="no_results",
                message=reply,
                needs_clarification=relaxation is not None,
                suggested_replies=["是", "暂不放宽"] if relaxation else [],
            )

        rank_input = MatchingToolInput(
            action="rank_candidates",
            user_id=user_id,
            intent=state.intent,
            candidate_ids=search["candidate_ids"],
            limit=max(limit * 3, limit),
        )
        rank_result = await trace.capture(
            step(6),
            "score_candidates",
            self.matching_tool.name,
            {"candidate_count": len(search["candidate_ids"])},
            lambda: self.matching_tool.execute(rank_input),
        )
        state.ranked_candidates = rank_result["ranked"]

        state.safety_result = await trace.capture(
            step(7),
            "safety_check",
            self.safety_tool.name,
            {"message_length": len(message)},
            lambda: self._check_safety(
                user_id, message, state.ranked_candidates, search_intent
            ),
        )
        if not state.safety_result["safe"]:
            selected: list[dict] = []
        else:
            safe_ids = set(state.safety_result["safe_candidate_ids"])
            selected = [
                item for item in state.ranked_candidates if item["id"] in safe_ids
            ][:limit]
        trace.add_observation(
            step(8), "rank_candidates", self.matching_tool.name, selected
        )

        recommendations = []
        icebreakers = []
        for candidate in selected:
            conversation_input = ConversationToolInput(
                action="generate_icebreaker",
                requester=state.profile,
                candidate=candidate,
                intent=state.intent,
            )
            conversation = await self.conversation_tool.execute(conversation_input)
            recommendation = {
                **candidate,
                "icebreaker": conversation["icebreaker"],
                "display_name": candidate.get("nickname", candidate["id"]),
                "score": candidate.get("total", 0.0),
                "score_breakdown": candidate.get("features", {}),
                "match_status": "matched"
                if self._has_active_match(user_id, candidate["id"])
                else "none",
            }
            recommendations.append(recommendation)
            icebreakers.append(conversation["icebreaker"])
        state.recommendations = recommendations
        trace.add_observation(
            step(9),
            "generate_recommendation",
            self.conversation_tool.name,
            recommendations,
        )

        if recommendations:
            await self.memory_tool.execute(
                MemoryToolInput(
                    action="record_recommendation",
                    user_id=user_id,
                    session_id=state.session_id,
                    candidate_ids=[item["id"] for item in recommendations],
                )
            )
        PartnerLoopService(self.db).record_request(
            user_id,
            state.session_id,
            state.intent,
            [item["id"] for item in recommendations],
        )
        self.memory_tool.manager.update_session(
            state.session_id,
            {
                "user_id": user_id,
                "goal": state.goal,
                "intent": state.intent,
                "candidate_ids": [item["id"] for item in recommendations],
                "recommendations": recommendations,
                "pending_slot": None,
                "pending_relaxation": None,
                "relaxed_slots": relaxed_slots,
            },
        )
        message_text = (
            f"为你找到 {len(recommendations)} 位候选人。"
            if recommendations
            else "候选人均未通过本轮安全检查。"
        )
        return self._response(
            state,
            response_type="recommendation" if recommendations else "safety_blocked",
            message=message_text,
            matches=recommendations,
            icebreakers=icebreakers,
            safety=state.safety_result,
        )

    async def _run_activity(self, state: AgentState, trace: AgentTrace, step) -> dict:
        safety = await trace.capture(
            step(1),
            "safety_check_message",
            self.safety_tool.name,
            {"message_length": len(state.user_message)},
            lambda: self._message_safety(state.user_id, state.user_message),
        )
        if not safety["safe"]:
            state.plan = state.plan[:1]
            return self._response(
                state,
                response_type="safety_blocked",
                message="这条请求包含风险信号，暂不执行活动查询。",
                safety=safety,
            )
        intent = await self._capture_llm(
            trace,
            step(2),
            "parse_intent",
            {"message_length": len(state.user_message)},
            lambda: parse_social_intent(state.user_message, self.llm),
        )
        state.intent = intent.model_dump()
        state.goal = "find_activity"
        activity_input = ActivityToolInput(
            campus=intent.campus, tag=intent.activity, limit=15
        )
        activities = await trace.capture(
            step(3),
            "search_activities",
            self.activity_tool.name,
            activity_input.model_dump(),
            lambda: self.activity_tool.execute(activity_input),
        )
        trace.add_observation(
            step(4), "generate_activity_response", "Agent", activities
        )
        self.memory_tool.manager.update_session(
            state.session_id,
            {
                "user_id": state.user_id,
                "goal": state.goal,
                "intent": state.intent,
                "activities": activities,
            },
        )
        reply = (
            f"找到 {len(activities)} 个符合条件的校园活动。"
            if activities
            else "暂时没有符合条件的公开活动，可以换个校区或活动关键词。"
        )
        return self._response(
            state,
            response_type="activities",
            message=reply,
            safety=safety,
            activities=activities,
        )

    async def _run_profile_update(
        self, state: AgentState, trace: AgentTrace, step
    ) -> dict:
        safety = await trace.capture(
            step(1),
            "safety_check_message",
            self.safety_tool.name,
            {"message_length": len(state.user_message)},
            lambda: self._message_safety(state.user_id, state.user_message),
        )
        if not safety["safe"]:
            state.plan = state.plan[:1]
            return self._response(
                state,
                response_type="safety_blocked",
                message="这条请求包含风险信号，画像没有更新。",
                safety=safety,
            )
        parsed = await self._capture_llm(
            trace,
            step(2),
            "parse_profile",
            {"message_length": len(state.user_message)},
            lambda: parse_profile_text(state.user_message, self.llm),
        )
        raw_updates = parsed.model_dump(exclude_none=True)
        updates = {key: value for key, value in raw_updates.items() if value != []}
        profile_input = ProfileToolInput(
            action="update_profile", user_id=state.user_id, updates=updates
        )
        profile = await trace.capture(
            step(3),
            "update_profile",
            self.profile_tool.name,
            {"fields": sorted(updates)},
            lambda: self.profile_tool.execute(profile_input),
        )
        state.profile = profile
        state.goal = "update_profile"
        state.intent = {"updates": updates}
        memory_input = MemoryToolInput(
            action="update_memory",
            user_id=state.user_id,
            session_id=state.session_id,
            values={
                "user_id": state.user_id,
                "goal": state.goal,
                "profile_updates": updates,
            },
        )
        await trace.capture(
            step(4),
            "update_memory",
            self.memory_tool.name,
            {"fields": sorted(updates)},
            lambda: self.memory_tool.execute(memory_input),
        )
        trace.add_observation(
            step(5), "generate_profile_response", "Agent", {"fields": sorted(updates)}
        )
        reply = (
            f"已更新画像字段：{'、'.join(sorted(updates))}。"
            if updates
            else "没有识别到可更新的公开画像字段，请说得更具体一些。"
        )
        return self._response(
            state,
            response_type="profile_updated" if updates else "clarification",
            message=reply,
            safety=safety,
            needs_clarification=not updates,
            profile=profile,
        )

    async def _run_explanation(
        self,
        state: AgentState,
        trace: AgentTrace,
        step,
        session: dict,
    ) -> dict:
        safety = await trace.capture(
            step(1),
            "safety_check_message",
            self.safety_tool.name,
            {"message_length": len(state.user_message)},
            lambda: self._message_safety(state.user_id, state.user_message),
        )

        async def load_session() -> dict:
            return session

        loaded = await trace.capture(
            step(2),
            "load_session",
            self.memory_tool.name,
            {"session_id": state.session_id},
            load_session,
        )
        recommendations = loaded.get("recommendations", [])
        target = next(
            (
                item
                for item in recommendations
                if item.get("id") in state.user_message
                or item.get("nickname", "") in state.user_message
            ),
            recommendations[0] if recommendations else None,
        )
        if target:
            reasons = target.get("reasons", [])
            reply = (
                f"推荐{target['nickname']}的主要原因是："
                + ("；".join(reasons) if reasons else "综合匹配分较高")
                + f"。综合分为 {target.get('total', 0):.2f}。"
            )
            state.intent = loaded.get("intent", {})
            state.goal = "explain_recommendation"
        else:
            reply = "这个会话里还没有可解释的推荐结果，请先让我帮你找搭子。"
            state.goal = "explain_recommendation"
        trace.add_observation(
            step(3),
            "explain_recommendation",
            "Agent",
            {"candidate_found": bool(target)},
        )
        return self._response(
            state,
            response_type="explanation",
            message=reply,
            safety=safety,
        )
