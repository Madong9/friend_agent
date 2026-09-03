from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_social_user
from ..database import get_db
from ..models import User
from ..schemas.conversation import ConversationRead, MessageCreate, MessageRead
from ..services import ConversationService
from ..tools.safety_tool import SafetyTool, SafetyToolInput

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _permission_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    return ConversationService(db).list_conversations(current_user.id)


@router.get("/{partner_id}/messages", response_model=list[MessageRead])
def list_messages(
    partner_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    before_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        return ConversationService(db).list_messages(
            current_user.id, partner_id, limit, before_id
        )
    except (PermissionError, ValueError) as exc:
        raise _permission_error(exc) from exc


@router.post("/{partner_id}/messages", response_model=MessageRead, status_code=201)
async def send_message(
    partner_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    service = ConversationService(db)
    try:
        service.require_active_match(current_user.id, partner_id)
    except (PermissionError, ValueError) as exc:
        raise _permission_error(exc) from exc
    safety = await SafetyTool(db).execute(
        SafetyToolInput(
            action="check_message", user_id=current_user.id, message=payload.body
        )
    )
    if not safety["safe"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "message requires safety review and was not sent",
                "risk_signals": safety["risk_signals"],
            },
        )
    return service.send_message(current_user.id, partner_id, payload.body, safety)


@router.post("/{partner_id}/read")
def mark_read(
    partner_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        count = ConversationService(db).mark_read(current_user.id, partner_id)
    except (PermissionError, ValueError) as exc:
        raise _permission_error(exc) from exc
    return {"marked_read": count}
