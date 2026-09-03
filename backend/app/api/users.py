from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user, is_allowed_school_email, require_self
from ..database import get_db
from ..llm import create_llm_provider
from ..models import User
from ..schemas.user import (
    PersonalityAnalysis,
    PersonalityAnalyzeRequest,
    ProfileParseResult,
    UserCreate,
    UserRead,
    UserUpdate,
)
from ..services.parsers import analyze_personality_text, parse_profile_text
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user_id = payload.id or f"user-{uuid4().hex[:12]}"
    if db.get(User, user_id):
        raise HTTPException(409, "user id already exists")
    if not is_allowed_school_email(payload.school_email):
        raise HTTPException(status_code=403, detail="school email domain not allowed")
    if db.query(User).filter(User.school_email == payload.school_email).first():
        raise HTTPException(409, "school email already exists")
    user = User(
        **payload.model_dump(exclude={"id", "password"}),
        id=user_id,
        password_hash=hash_password(payload.password),
        verified=True,
        campus_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


class NaturalProfileUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    apply: bool = True


@router.post("/me/profile/parse", response_model=ProfileParseResult)
async def parse_and_update_my_profile(
    payload: NaturalProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parsed = await parse_profile_text(payload.text, create_llm_provider())
    if payload.apply:
        for field, value in parsed.model_dump(exclude_none=True).items():
            if value:
                setattr(current_user, field, value)
        db.commit()
    return parsed


@router.post("/me/personality/analyze", response_model=PersonalityAnalysis)
async def analyze_my_personality(
    payload: PersonalityAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.consent:
        raise HTTPException(400, "explicit personality analysis consent is required")
    analysis = await analyze_personality_text(payload.text, create_llm_provider())
    from ..models.user import utcnow

    current_user.personality_consent = True
    current_user.personality_traits = analysis.traits.model_dump()
    current_user.personality_summary = analysis.summary
    current_user.personality_updated_at = utcnow()
    db.commit()
    return analysis


@router.delete("/me/personality", status_code=204)
def clear_my_personality(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.personality_consent = False
    current_user.personality_traits = {}
    current_user.personality_summary = ""
    current_user.personality_updated_at = None
    db.commit()


@router.post("/{user_id}/profile/parse", response_model=ProfileParseResult)
async def parse_and_update_profile(
    user_id: str,
    payload: NaturalProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_self(current_user, user_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    parsed = await parse_profile_text(payload.text, create_llm_provider())
    if payload.apply:
        for field, value in parsed.model_dump(exclude_none=True).items():
            if value:
                setattr(user, field, value)
        db.commit()
    return parsed
