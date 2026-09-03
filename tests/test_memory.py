from backend.app.memory import MemoryManager


def test_memory_load_and_session_are_separate(db, sample_users):
    user, candidate, _ = sample_users
    memory = MemoryManager(db)
    memory.record_feedback(user.id, candidate.id, "PASS")
    loaded = memory.load_user_memory(user.id)
    assert loaded["profile"]["nickname"] == "甲"
    assert loaded["interactions"][0]["kind"] == "PASS"
    assert candidate.id in memory.get_recent_candidates(user.id)
    memory.update_session(
        "session-x", {"user_id": user.id, "last_goal": "find_partner"}
    )
    assert memory.get_session("session-x")["last_goal"] == "find_partner"


def test_only_latest_recommendation_page_is_suppressed(db, sample_users):
    user, first, second = sample_users
    memory = MemoryManager(db)
    memory.record_recommendation(user.id, [first.id], "older-session")
    memory.record_recommendation(user.id, [second.id], "latest-session")

    recent = memory.get_recent_candidates(user.id)
    assert second.id in recent
    assert first.id not in recent

    memory.record_feedback(user.id, first.id, "PASS")
    assert {first.id, second.id} <= set(memory.get_recent_candidates(user.id))
