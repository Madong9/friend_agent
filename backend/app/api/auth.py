from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user, is_allowed_school_email
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas.auth import (
    WechatLoginRequest,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
)
from ..schemas.user import UserRead
from ..security import (
    DUMMY_PASSWORD_HASH,
    JWT_ALGORITHM,
    create_access_token,
    verify_password,
)
from ..services.wechat_identity import WechatIdentityError, WechatIdentityService

router = APIRouter(prefix="/auth", tags=["authentication"])

USTC_CAS_STATE_TTL_MINUTES = 10


def _build_cas_state(next_path: str | None, request: Request) -> str:
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=USTC_CAS_STATE_TTL_MINUTES)
    payload = {
        "typ": "ustc-cas-state",
        "iat": issued_at,
        "exp": expires_at,
        "next": _sanitize_next_path(next_path),
        "redirect": str(request.url_for("ustc_cas_callback")),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _decode_cas_state(state: str | None) -> dict[str, Any]:
    if not state:
        raise HTTPException(status_code=400, detail="missing CAS state")
    settings = get_settings()
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "typ", "next", "redirect"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail="invalid CAS state") from exc
    if payload.get("typ") != "ustc-cas-state":
        raise HTTPException(status_code=400, detail="invalid CAS state")
    return payload


def _sanitize_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/"
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


def _pick_first(attributes: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = attributes.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_cas_attributes(xml_text: str) -> dict[str, str]:
    root = ElementTree.fromstring(xml_text)
    namespaces = {
        "cas": "http://www.yale.edu/tp/cas",
    }
    success = root.find("cas:authenticationSuccess", namespaces)
    if success is None:
        failure = root.find("cas:authenticationFailure", namespaces)
        message = (
            (failure.text or "CAS authentication failed").strip()
            if failure is not None
            else "CAS authentication failed"
        )
        raise HTTPException(status_code=401, detail=message)
    attributes: dict[str, str] = {}
    attributes_node = success.find("cas:attributes", namespaces)
    if attributes_node is not None:
        for child in list(attributes_node):
            tag = child.tag.split("}", 1)[-1]
            text = (child.text or "").strip()
            if text:
                attributes[tag] = text
    user = success.findtext("cas:user", default="", namespaces=namespaces).strip()
    if user:
        attributes.setdefault("user", user)
    return attributes


def _resolve_or_create_ustc_user(db: Session, attributes: dict[str, str]) -> User:
    school_email = _pick_first(attributes, ("mail", "email", "userEmail", "user"))
    school_uid = _pick_first(
        attributes, ("uid", "studentId", "staffId", "casUser", "user")
    )
    display_name = _pick_first(attributes, ("displayName", "cn", "name", "user"))
    query = db.query(User)
    user = None
    if school_email:
        user = query.filter(User.school_email == school_email).one_or_none()
    if user is None and school_uid:
        user = query.filter(User.school_uid == school_uid).one_or_none()
    if user is not None:
        user.verified = True
        user.campus_verified = True
        if school_email and user.school_email is None:
            user.school_email = school_email
        if school_uid and user.school_uid is None:
            user.school_uid = school_uid
        if display_name and user.school_display_name is None:
            user.school_display_name = display_name
        if user.identity_provider != "ustc-cas":
            user.identity_provider = "ustc-cas"
        if user.school != "中国科学技术大学":
            user.school = "中国科学技术大学"
        return user

    if not school_email and not school_uid:
        raise HTTPException(
            status_code=400, detail="CAS response did not include a school identifier"
        )
    local_part = (
        school_email.split("@", 1)[0] if school_email else (school_uid or "ustc")
    )
    candidate_id = f"ustc-{local_part}"
    suffix = 1
    while db.get(User, candidate_id) is not None:
        suffix += 1
        candidate_id = f"ustc-{local_part}-{suffix}"
    user = User(
        id=candidate_id,
        nickname=display_name or f"USTC{local_part[-4:]}" if local_part else "USTC同学",
        school_email=school_email,
        school_uid=school_uid,
        school_display_name=display_name,
        identity_provider="ustc-cas",
        school="中国科学技术大学",
        campus="待完善",
        grade="待完善",
        major="待完善",
        recommendation_enabled=True,
        verified=True,
        campus_verified=True,
    )
    db.add(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = None
    if payload.school_email is not None:
        if not is_allowed_school_email(payload.school_email):
            raise HTTPException(
                status_code=403, detail="school email domain not allowed"
            )
        user = (
            db.query(User)
            .filter(User.school_email == payload.school_email)
            .one_or_none()
        )
    elif payload.user_id is not None:
        user = db.get(User, payload.user_id)
    encoded_password = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, encoded_password)
    if user is None or not password_valid or not user.verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid user id or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(
            user.id, settings, token_version=user.token_version
        ),
        expires_in=settings.jwt_access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/wechat", response_model=TokenResponse)
async def wechat_login(payload: WechatLoginRequest, db: Session = Depends(get_db)):
    service = WechatIdentityService(db)
    try:
        identity = await service.code_to_openid(payload.code)
    except WechatIdentityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = service.resolve_or_create_user(identity.openid, payload.nickname)
    db.commit()
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(
            user.id, settings, token_version=user.token_version
        ),
        expires_in=settings.jwt_access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", response_model=LogoutResponse)
def logout(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    current_user.token_version += 1
    from ..models.user import utcnow

    current_user.last_token_revoked_at = utcnow()
    db.commit()
    return LogoutResponse()


@router.get("/ustc/login")
def ustc_login(request: Request, next: str | None = None):
    settings = get_settings()
    callback_service = str(request.url_for("ustc_cas_callback"))
    state = _build_cas_state(next, request)
    login_url = f"{settings.ustc_cas_login_url}?{urlencode({'service': callback_service, 'state': state})}"
    return RedirectResponse(login_url, status_code=302)


@router.get("/ustc/callback", name="ustc_cas_callback")
def ustc_cas_callback(
    request: Request,
    ticket: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    try:
        if not ticket:
            raise HTTPException(status_code=400, detail="missing CAS ticket")
        state_payload = _decode_cas_state(state)
        service_url = state_payload["redirect"]
        validate_url = settings.ustc_cas_validate_url
        params = {"ticket": ticket, "service": service_url}
        response = httpx.get(validate_url, params=params, timeout=10.0)
        response.raise_for_status()
        attributes = _parse_cas_attributes(response.text)
        user = _resolve_or_create_ustc_user(db, attributes)
        db.commit()
        token = create_access_token(user.id, settings, token_version=user.token_version)
        redirect_path = state_payload.get("next") or "/"
        target = (
            f"{settings.frontend_base_url}{redirect_path}#access_token={token}"
            "&token_type=bearer"
        )
        return RedirectResponse(target, status_code=302)
    except (
        HTTPException,
        httpx.HTTPError,
        ElementTree.ParseError,
        jwt.InvalidTokenError,
    ) as exc:
        detail = (
            exc.detail
            if isinstance(exc, HTTPException)
            else "USTC 登录失败，请稍后重试。"
        )
        error_target = f"{settings.frontend_base_url}/?{urlencode({'auth_error': detail, 'auth_stage': 'ustc'})}"
        return RedirectResponse(error_target, status_code=302)
