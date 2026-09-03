from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_social_user
from ..database import get_db
from ..models import User
from ..schemas.feedback import BlockCreate, FeedbackCreate, ReportCreate
from ..services import SocialService

router = APIRouter(tags=["feedback & safety"])


@router.post("/feedback")
def feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        match = SocialService(db).record_feedback(
            current_user.id, payload.candidate_id, payload.feedback.value
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    demo_match = False
    if match is not None:
        user_a = db.get(User, match.user_a_id)
        user_b = db.get(User, match.user_b_id)
        demo_match = bool(
            user_a is not None
            and user_b is not None
            and (user_a.is_mock or user_b.is_mock)
        )
    return {
        "recorded": True,
        "feedback": payload.feedback.value,
        "matched": match is not None,
        "chat_enabled": match is not None and not demo_match,
        "demo_match": demo_match,
    }


@router.post("/block", status_code=201)
def block(
    payload: BlockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        item = SocialService(db).block_user(current_user.id, payload.blocked_user_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"blocked": True, "block_id": item.id}


@router.post("/report", status_code=201)
def report(
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        item = SocialService(db).report_user(
            current_user.id,
            payload.reported_user_id,
            payload.reason,
            payload.category,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"reported": True, "report_id": item.id, "status": item.status}
