from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..tools.activity_tool import ActivityTool, ActivityToolInput

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
async def list_activities(
    campus: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return await ActivityTool(db).execute(
        ActivityToolInput(campus=campus, tag=tag, limit=limit)
    )
