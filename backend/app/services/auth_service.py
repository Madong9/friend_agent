"""Identity resolution shared across the backend.

The unified entry point is `resolve_current_user_id`. In development, DEV_AUTH_MODE
short-circuits authentication to a fixed user for local testing without WeChat; in any
other environment it requires a valid bearer token whose `sub` is the internal user id.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from ..config import get_settings


@dataclass(frozen=True)
class Identity:
    user_id: str
    source: str  # "jwt" | "dev"


def resolve_current_user_id(token_sub: str | None) -> Identity:
    """Resolve the internal user id from trusted context.

    Never trusts a client-supplied arbitrary user id: either the signed token subject
    or the dev-configured identity is used.
    """
    settings = get_settings()
    if token_sub:
        return Identity(user_id=token_sub, source="jwt")
    if settings.dev_auth_mode and settings.app_env.lower() != "production":
        settings.validate_runtime()
        user = settings.dev_user_id
        if settings.dev_auth_mode and user:
            return Identity(user_id=user, source="dev")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="valid bearer token required",
        headers={"WWW-Authenticate": "Bearer"},
    )
