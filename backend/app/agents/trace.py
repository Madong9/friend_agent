from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AgentTraceRecord


def _summary(value: Any) -> dict:
    if isinstance(value, list):
        return {"type": "list", "count": len(value)}
    if isinstance(value, dict):
        summary: dict[str, Any] = {"keys": sorted(value.keys())[:12]}
        for key in ("retrieved_count", "filtered_count", "recorded"):
            if key in value:
                summary[key] = value[key]
        if "ranked" in value and isinstance(value["ranked"], list):
            summary["result_count"] = len(value["ranked"])
        return summary
    return {"type": type(value).__name__}


class TraceEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), exclude=True)
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), exclude=True
    )
    step: int
    action: str
    tool: str
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    status: str
    duration: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    session_id: str
    user_id: str
    entries: list[TraceEntry] = Field(default_factory=list)

    async def capture(
        self,
        step: int,
        action: str,
        tool: str,
        tool_input: Any,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        started = perf_counter()
        try:
            result = await operation()
        except Exception as exc:
            self.entries.append(
                TraceEntry(
                    step=step,
                    action=action,
                    tool=tool,
                    input_summary=_summary(tool_input),
                    output_summary={"error_type": type(exc).__name__},
                    status="error",
                    duration=round(perf_counter() - started, 6),
                )
            )
            raise
        self.entries.append(
            TraceEntry(
                step=step,
                action=action,
                tool=tool,
                input_summary=_summary(tool_input),
                output_summary=_summary(result),
                status="success",
                duration=round(perf_counter() - started, 6),
            )
        )
        return result

    def add_observation(
        self, step: int, action: str, tool: str, output: Any, duration: float = 0.0
    ) -> None:
        self.entries.append(
            TraceEntry(
                step=step,
                action=action,
                tool=tool,
                output_summary=_summary(output),
                status="success",
                duration=duration,
            )
        )


class TraceStore:
    """Database-backed append/merge store for restart and multi-worker safety."""

    def __init__(
        self,
        db: Session,
        trace_ttl: timedelta | None = None,
        max_entries: int | None = None,
    ):
        settings = get_settings()
        self.db = db
        self.trace_ttl = trace_ttl or timedelta(days=settings.agent_trace_ttl_days)
        self.max_entries = max_entries or settings.agent_trace_max_entries

    def save(self, trace: AgentTrace) -> None:
        """Merge by event ID so stale workers cannot overwrite each other's entries."""
        if getattr(self.db, "is_cloudbase_http", False):
            result = self.db.rpc(
                "campus_agent_trace_save",
                {
                    "p_session_id": trace.session_id,
                    "p_user_id": trace.user_id,
                    "p_entries": [
                        self._serialize_entry(entry) for entry in trace.entries
                    ],
                    "p_ttl_seconds": int(self.trace_ttl.total_seconds()),
                    "p_max_entries": self.max_entries,
                },
            )
            if result.get("status") == "forbidden":
                raise PermissionError("cannot overwrite another user's agent trace")
            if result.get("status") != "saved":
                raise RuntimeError("agent trace save failed")
            return
        self.cleanup_expired_traces()
        incoming = [self._serialize_entry(entry) for entry in trace.entries]
        for _attempt in range(5):
            self.db.expire_all()
            record = self.db.get(AgentTraceRecord, trace.session_id)
            now = datetime.now(timezone.utc)
            expires_at = now + self.trace_ttl
            if record is not None and self._is_expired(record.expires_at, now):
                self.db.delete(record)
                self.db.commit()
                record = None

            if record is None:
                entries = self._merge_entries([], incoming)
                self.db.add(
                    AgentTraceRecord(
                        session_id=trace.session_id,
                        user_id=trace.user_id,
                        entries=entries,
                        version=1,
                        created_at=now,
                        updated_at=now,
                        expires_at=expires_at,
                    )
                )
                try:
                    self.db.commit()
                    return
                except IntegrityError:
                    self.db.rollback()
                    continue

            if record.user_id != trace.user_id:
                raise PermissionError("cannot overwrite another user's agent trace")
            merged = self._merge_entries(record.entries or [], incoming)
            expected_version = record.version
            result = self.db.execute(
                update(AgentTraceRecord)
                .where(
                    AgentTraceRecord.session_id == trace.session_id,
                    AgentTraceRecord.version == expected_version,
                )
                .values(
                    entries=merged,
                    version=expected_version + 1,
                    updated_at=now,
                    expires_at=expires_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                self.db.commit()
                return
            self.db.rollback()
        raise RuntimeError("agent trace update conflicted too many times")

    def get(self, session_id: str) -> AgentTrace | None:
        self.db.expire_all()
        record = self.db.get(AgentTraceRecord, session_id)
        if record is None:
            return None
        if self._is_expired(record.expires_at):
            self.db.delete(record)
            self.db.commit()
            return None
        entries = [
            self._deserialize_entry(item, index)
            for index, item in enumerate(
                self._merge_entries(record.entries or [], []), start=1
            )
        ]
        return AgentTrace(
            session_id=record.session_id, user_id=record.user_id, entries=entries
        )

    def cleanup_expired_traces(self) -> int:
        result = self.db.execute(
            delete(AgentTraceRecord).where(
                AgentTraceRecord.expires_at <= datetime.now(timezone.utc)
            )
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def _merge_entries(
        self, stored: list[dict[str, Any]], incoming: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        by_event_id = {
            item["event_id"]: dict(item)
            for item in [*stored, *incoming]
            if item.get("event_id")
        }
        ordered = sorted(
            by_event_id.values(),
            key=lambda item: (item.get("recorded_at", ""), item["event_id"]),
        )[-self.max_entries :]
        for step, item in enumerate(ordered, start=1):
            item["step"] = step
        return ordered

    @staticmethod
    def _serialize_entry(entry: TraceEntry) -> dict[str, Any]:
        return {
            "event_id": entry.event_id,
            "recorded_at": entry.recorded_at.isoformat(),
            "step": entry.step,
            "action": entry.action,
            "tool": entry.tool,
            "input_summary": entry.input_summary,
            "output_summary": entry.output_summary,
            "status": entry.status,
            "duration": entry.duration,
            "metadata": entry.metadata,
        }

    @staticmethod
    def _deserialize_entry(item: dict[str, Any], step: int) -> TraceEntry:
        return TraceEntry(
            event_id=item["event_id"],
            recorded_at=datetime.fromisoformat(item["recorded_at"]),
            step=step,
            action=item["action"],
            tool=item["tool"],
            input_summary=item.get("input_summary", {}),
            output_summary=item.get("output_summary", {}),
            status=item["status"],
            duration=item["duration"],
            metadata=item.get("metadata", {}),
        )

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= now
