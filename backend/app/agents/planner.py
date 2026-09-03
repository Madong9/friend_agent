from __future__ import annotations

from .state import AgentState
from .router import AgentTask


class Planner:
    """Create a task-specific, inspectable plan and allow bounded replanning."""

    BASE_ACTIONS = [
        ("load_profile", "ProfileTool"),
        ("load_memory", "MemoryTool"),
        ("parse_intent", "LLM"),
        ("search_candidates", "MatchingTool"),
        ("hard_filter", "MatchingTool"),
        ("score_candidates", "MatchingTool"),
        ("safety_check", "SafetyTool"),
        ("rank_candidates", "MatchingTool"),
        ("generate_recommendation", "ConversationTool"),
    ]

    TASK_ACTIONS = {
        AgentTask.FIND_PARTNER: BASE_ACTIONS,
        AgentTask.FIND_ACTIVITY: [
            ("safety_check_message", "SafetyTool"),
            ("parse_intent", "LLM"),
            ("search_activities", "ActivityTool"),
            ("generate_activity_response", "Agent"),
        ],
        AgentTask.UPDATE_PROFILE: [
            ("safety_check_message", "SafetyTool"),
            ("parse_profile", "LLM"),
            ("update_profile", "ProfileTool"),
            ("update_memory", "MemoryTool"),
            ("generate_profile_response", "Agent"),
        ],
        AgentTask.EXPLAIN_RECOMMENDATION: [
            ("safety_check_message", "SafetyTool"),
            ("load_session", "MemoryTool"),
            ("explain_recommendation", "Agent"),
        ],
        AgentTask.CONTINUE_CLARIFICATION: [
            ("load_profile", "ProfileTool"),
            ("load_memory", "MemoryTool"),
            ("merge_clarification", "LLM"),
            ("search_candidates", "MatchingTool"),
            ("hard_filter", "MatchingTool"),
            ("score_candidates", "MatchingTool"),
            ("safety_check", "SafetyTool"),
            ("rank_candidates", "MatchingTool"),
            ("generate_recommendation", "ConversationTool"),
        ],
        AgentTask.CONFIRM_RELAXATION: [
            ("load_profile", "ProfileTool"),
            ("load_memory", "MemoryTool"),
            ("apply_constraint_relaxation", "Agent"),
            ("search_candidates", "MatchingTool"),
            ("hard_filter", "MatchingTool"),
            ("score_candidates", "MatchingTool"),
            ("safety_check", "SafetyTool"),
            ("rank_candidates", "MatchingTool"),
            ("generate_recommendation", "ConversationTool"),
        ],
    }

    def create_plan(
        self, state: AgentState, task: AgentTask = AgentTask.FIND_PARTNER
    ) -> list[dict]:
        actions = self.TASK_ACTIONS.get(task, self.BASE_ACTIONS)
        return [
            {"step": index, "action": action, "tool": tool}
            for index, (action, tool) in enumerate(actions, 1)
        ]

    def replan_for_clarification(self, state: AgentState) -> list[dict]:
        parse_action = next(
            (
                action
                for action in ("parse_intent", "merge_clarification")
                if any(item["action"] == action for item in state.plan)
            ),
            "parse_intent",
        )
        return self._replace_after(
            state.plan,
            parse_action,
            [("ask_clarification", "Agent")],
        )

    def replan_for_no_candidates(self, state: AgentState) -> list[dict]:
        return self._replace_after(
            state.plan,
            "hard_filter",
            [
                ("observe_no_candidates", "MatchingTool"),
                ("request_constraint_relaxation", "Agent"),
            ],
        )

    @staticmethod
    def _replace_after(
        plan: list[dict], action: str, replacements: list[tuple[str, str]]
    ) -> list[dict]:
        cutoff = next(
            (index for index, item in enumerate(plan) if item["action"] == action),
            len(plan) - 1,
        )
        actions = [(item["action"], item["tool"]) for item in plan[: cutoff + 1]]
        actions.extend(replacements)
        return [
            {"step": index, "action": item_action, "tool": tool}
            for index, (item_action, tool) in enumerate(actions, 1)
        ]
