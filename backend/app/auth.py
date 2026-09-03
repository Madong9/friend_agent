"""FastAPI authentication dependencies and authorization helpers."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import User
from .security import TokenError, decode_access_token
from .services.auth_service import resolve_current_user_id

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="valid bearer token required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def select_business_credentials(
    gateway_credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    campus_authorization: str | None = Header(
        default=None, alias="X-Campus-Authorization"
    ),
) -> HTTPAuthorizationCredentials | None:
    """Select the application JWT without trusting the transport header itself.

    CloudBase SDK uses Authorization for its gateway credential. In that transport
    only, the Mini Program forwards the existing application bearer token through
    X-Campus-Authorization. Parsing it here still feeds the exact same JWT decoder,
    token-version check and user lookup used by the normal Authorization path.
    """

    if campus_authorization is None:
        return gateway_credentials
    scheme, separator, token = campus_authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token.strip())


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        select_business_credentials
    ),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = _unauthorized()
    token_payload = None
    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise unauthorized
        try:
            token_payload = decode_access_token(credentials.credentials)
        except TokenError as exc:
            # An explicitly supplied invalid token must never silently become
            # DEV_USER_ID, even when local development auth is enabled.
            raise unauthorized from exc
    identity = resolve_current_user_id(
        token_payload["sub"] if token_payload is not None else None
    )
    user = db.get(User, identity.user_id)
    if user is None or not user.verified:
        raise unauthorized
    if token_payload is not None and user.token_version != token_payload["ver"]:
        raise unauthorized
    return user


def get_social_user(current_user: User = Depends(get_current_user)) -> User:
    if get_settings().require_campus_verification and not current_user.campus_verified:
        raise HTTPException(
            status_code=403,
            detail="campus identity verification is required for social features",
        )
    return current_user


def is_allowed_school_email(email: str) -> bool:
    settings = get_settings()
    return any(
        email.lower().endswith(f"@{domain.lower()}")
        for domain in settings.school_email_domains
    )


def school_email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def require_self(current_user: User, requested_user_id: str) -> None:
    if current_user.id != requested_user_id:
        raise HTTPException(status_code=403, detail="cannot access another user's data")
