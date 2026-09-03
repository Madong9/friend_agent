from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_social_user, require_self
from ..database import get_db
from ..models import Match, User
from ..services import SocialService
from ..tools.privacy import public_user

router = APIRouter(prefix="/matches", tags=["matches"])


def _serialize_matches(user_id: str, db: Session) -> list[dict]:
    output = []
    for item in SocialService(db).list_matches(user_id):
        partner_id = item.user_b_id if item.user_a_id == user_id else item.user_a_id
        partner = db.get(User, partner_id)
        requester = db.get(User, user_id)
        if partner:
            demo = bool(
                requester is not None and (requester.is_mock or partner.is_mock)
            )
            output.append(
                {
                    "match_id": item.id,
                    "status": item.status,
                    "chat_enabled": not demo,
                    "demo_match": demo,
                    "partner": public_user(partner),
                    "created_at": item.created_at,
                }
            )
    return output


@router.get("/me")
def get_my_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    return _serialize_matches(current_user.id, db)


@router.get("/me/{match_id}")
def get_my_match_detail(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "match not found")
    if current_user.id not in {match.user_a_id, match.user_b_id}:
        raise HTTPException(403, "cannot access another user's match")
    partner_id = (
        match.user_b_id if match.user_a_id == current_user.id else match.user_a_id
    )
    partner = db.get(User, partner_id)
    if partner is None:
        raise HTTPException(404, "partner not found")
    demo = bool(current_user.is_mock or partner.is_mock)
    return {
        "match_id": match.id,
        "status": match.status,
        "chat_enabled": not demo,
        "demo_match": demo,
        "partner": public_user(partner),
        "created_at": match.created_at,
    }


@router.get("/{user_id}")
def get_matches(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    require_self(current_user, user_id)
    if db.get(User, user_id) is None:
        raise HTTPException(404, "user not found")
    return _serialize_matches(user_id, db)
