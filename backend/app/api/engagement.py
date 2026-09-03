from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_social_user
from ..database import get_db
from ..models import User
from ..schemas.engagement import (
    NotificationRead,
    PartnerRequestRead,
    PartnerRequestStatusUpdate,
)
from ..services.partner_loop import PartnerLoopService

router = APIRouter(tags=["partner engagement"])


@router.get("/partner-requests", response_model=list[PartnerRequestRead])
def list_partner_requests(
    db: Session = Depends(get_db), current_user: User = Depends(get_social_user)
):
    return PartnerLoopService(db).list_requests(current_user.id)


@router.patch("/partner-requests/{request_id}", response_model=PartnerRequestRead)
def update_partner_request(
    request_id: int,
    payload: PartnerRequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        return PartnerLoopService(db).set_request_status(
            current_user.id, request_id, payload.status
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    return PartnerLoopService(db).list_notifications(current_user.id, unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    try:
        return PartnerLoopService(db).mark_notification_read(
            current_user.id, notification_id
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
