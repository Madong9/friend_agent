from backend.app.agents import AgentState, Planner


def test_agent_plan_has_required_order():
    state = AgentState(session_id="s", user_id="u", user_message="找搭子")
    plan = Planner().create_plan(state)
    assert [item["step"] for item in plan] == list(range(1, 10))
    assert [item["action"] for item in plan][:4] == [
        "load_profile",
        "load_memory",
        "parse_intent",
        "search_candidates",
    ]
