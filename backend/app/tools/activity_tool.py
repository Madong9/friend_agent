from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Activity
from .base import BaseTool


class ActivityToolInput(BaseModel):
    campus: str | None = None
    tag: str | None = None
    limit: int = Field(default=15, ge=1, le=50)


class ActivityTool(BaseTool):
    name = "ActivityTool"
    description = "Find public mock campus activities by campus and tag."
    input_schema = ActivityToolInput

    def __init__(self, db: Session):
        self.db = db

    async def execute(self, tool_input: ActivityToolInput) -> list[dict]:
        activities = list(
            self.db.scalars(select(Activity).where(Activity.public.is_(True)))
        )
        if tool_input.campus:
            activities = [
                item for item in activities if item.campus == tool_input.campus
            ]
        if tool_input.tag:
            activities = [
                item
                for item in activities
                if tool_input.tag in item.tags or tool_input.tag in item.name
            ]
        return [
            {
                "id": item.id,
                "name": item.name,
                "campus": item.campus,
                "location": item.location,
                "time": item.time,
                "tags": item.tags,
                "capacity": item.capacity,
            }
            for item in activities[: tool_input.limit]
        ]
