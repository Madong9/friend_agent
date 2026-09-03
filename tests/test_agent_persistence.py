from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from backend.app.agents import AgentTrace, CampusSocialAgent, TraceStore
from backend.app.llm import MockLLMProvider
from backend.app.memory import MemoryManager, SessionBusyError
from backend.app.models import AgentSessionRecord, AgentTraceRecord


@pytest.mark.asyncio
async def test_session_and_trace_survive_new_agent_and_database_session(
    db, sample_users
):
    first = await CampusSocialAgent(db, MockLLMProvider()).run("a", "找羽毛球搭子")
    assert first["response_type"] == "clarification"

    with Session(bind=db.get_bind(), expire_on_commit=False) as second_worker_db:
        second = await CampusSocialAgent(second_worker_db, MockLLMProvider()).run(
            "a", "周六下午", session_id=first["session_id"]
        )
        assert second["response_type"] == "recommendation"
        assert second["matches"][0]["id"] == "b"

    with Session(bind=db.get_bind(), expire_on_commit=False) as reader_db:
        session = MemoryManager(reader_db).get_session(first["session_id"])
        trace = TraceStore(reader_db).get(first["session_id"])
        assert session["turn_count"] == 2
        assert session["intent"]["availability"] == ["周六下午"]
        assert trace is not None
        assert [entry.step for entry in trace.entries] == list(range(1, 14))


def test_independent_workers_merge_session_fields(db, sample_users):
    with Session(bind=db.get_bind(), expire_on_commit=False) as first_worker_db:
        first_worker = MemoryManager(first_worker_db)
        first_worker.update_session(
            "shared-session", {"user_id": "a", "first_worker": True}
        )

    with Session(bind=db.get_bind(), expire_on_commit=False) as second_worker_db:
        second_worker = MemoryManager(second_worker_db)
        second_worker.update_session("shared-session", {"second_worker": True})

    state = MemoryManager(db).get_session("shared-session")
    assert state["first_worker"] is True
    assert state["second_worker"] is True
    assert db.get(AgentSessionRecord, "shared-session").version == 2


def test_stale_trace_writers_merge_by_event_id(db, sample_users):
    initial = AgentTrace(session_id="shared-trace", user_id="a")
    initial.add_observation(1, "initial", "Agent", {"ok": True})
    TraceStore(db).save(initial)

    with Session(bind=db.get_bind(), expire_on_commit=False) as other_worker_db:
        first_copy = TraceStore(db).get("shared-trace")
        second_copy = TraceStore(other_worker_db).get("shared-trace")
        assert first_copy is not None and second_copy is not None

        first_copy.add_observation(2, "worker_one", "Agent", {})
        second_copy.add_observation(2, "worker_two", "Agent", {})
        TraceStore(db).save(first_copy)
        TraceStore(other_worker_db).save(second_copy)

    merged = TraceStore(db).get("shared-trace")
    assert merged is not None
    assert {entry.action for entry in merged.entries} == {
        "initial",
        "worker_one",
        "worker_two",
    }
    assert [entry.step for entry in merged.entries] == [1, 2, 3]
    assert "event_id" not in merged.model_dump()["entries"][0]


def test_database_turn_lease_rejects_concurrent_session_turns(db, sample_users):
    first_worker = MemoryManager(db)
    first_worker.update_session("leased-session", {"user_id": "a"})
    first_worker.acquire_session_turn("leased-session", "a", "turn-one")

    with Session(bind=db.get_bind(), expire_on_commit=False) as other_worker_db:
        second_worker = MemoryManager(other_worker_db)
        with pytest.raises(SessionBusyError):
            second_worker.acquire_session_turn("leased-session", "a", "turn-two")

    first_worker.release_session_turn("leased-session", "turn-one")
    with Session(bind=db.get_bind(), expire_on_commit=False) as other_worker_db:
        second_worker = MemoryManager(other_worker_db)
        second_worker.acquire_session_turn("leased-session", "a", "turn-two")
        second_worker.release_session_turn("leased-session", "turn-two")


def test_expired_session_and_trace_are_removed(db, sample_users):
    memory = MemoryManager(db)
    memory.update_session("expired-session", {"user_id": "a", "value": 1})
    trace = AgentTrace(session_id="expired-session", user_id="a")
    trace.add_observation(1, "temporary", "Agent", {})
    TraceStore(db).save(trace)

    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.get(AgentSessionRecord, "expired-session").expires_at = past
    db.get(AgentTraceRecord, "expired-session").expires_at = past
    db.commit()

    assert memory.get_session("expired-session") == {}
    assert TraceStore(db).get("expired-session") is None
    assert db.get(AgentSessionRecord, "expired-session") is None
    assert db.get(AgentTraceRecord, "expired-session") is None
