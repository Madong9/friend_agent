from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from backend.app.agents.trace import AgentTrace, TraceEntry, TraceStore
from backend.app.memory.manager import MemoryManager, SessionBusyError
from backend.app.services.social import SocialService


class RpcSession:
    is_cloudbase_http = True

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        self.rows = {}

    def rpc(self, name, parameters):
        self.calls.append((name, parameters))
        response = self.responses.get(name, {"status": "ok"})
        return response(parameters) if callable(response) else response

    def get(self, model, primary_key):
        return self.rows.get((model.__name__, primary_key))


def test_memory_session_mutations_use_atomic_rpc_functions():
    db = RpcSession(
        {
            "campus_agent_session_update": {"status": "created"},
            "campus_agent_session_acquire": {"status": "acquired"},
            "campus_agent_session_release": {"status": "released"},
        }
    )
    manager = MemoryManager(db, session_ttl=timedelta(minutes=30))
    manager.update_session("session-1", {"user_id": "user001"})
    manager.acquire_session_turn("session-1", "user001", "turn-1")
    manager.release_session_turn("session-1", "turn-1")
    assert [item[0] for item in db.calls] == [
        "campus_agent_session_update",
        "campus_agent_session_acquire",
        "campus_agent_session_release",
    ]
    assert db.calls[0][1]["p_ttl_seconds"] == 1800


def test_busy_cloud_session_maps_to_existing_business_exception():
    db = RpcSession({"campus_agent_session_acquire": {"status": "busy"}})
    manager = MemoryManager(db)
    try:
        manager.acquire_session_turn("session-1", "user001", "turn-1")
    except SessionBusyError:
        pass
    else:
        raise AssertionError("busy RPC status must retain SessionBusyError behavior")


def test_trace_store_uses_atomic_merge_rpc():
    db = RpcSession({"campus_agent_trace_save": {"status": "saved"}})
    store = TraceStore(db, trace_ttl=timedelta(days=2), max_entries=25)
    trace = AgentTrace(
        session_id="session-1",
        user_id="user001",
        entries=[
            TraceEntry(
                step=1,
                action="load_profile",
                tool="ProfileTool",
                status="success",
                duration=0.01,
            )
        ],
    )
    store.save(trace)
    name, payload = db.calls[0]
    assert name == "campus_agent_trace_save"
    assert payload["p_max_entries"] == 25
    assert payload["p_ttl_seconds"] == 172800
    assert payload["p_entries"][0]["action"] == "load_profile"


def test_feedback_and_block_use_transaction_rpc_without_local_partial_writes():
    db = RpcSession(
        {
            "campus_record_feedback": {"status": "recorded", "match_id": None},
            "campus_block_user": {"status": "blocked", "block_id": 7},
        }
    )
    db.rows[("Block", 7)] = SimpleNamespace(
        id=7, blocker_id="user001", blocked_id="user002"
    )
    service = SocialService(db)
    assert service.record_feedback("user001", "user002", "LIKE") is None
    block = service.block_user("user001", "user002")
    assert block.id == 7
    assert [item[0] for item in db.calls] == [
        "campus_record_feedback",
        "campus_block_user",
    ]
