"""DEV_AUTH_MODE identity resolution for local development without WeChat."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.config import Settings, get_settings
from backend.app.services.auth_service import resolve_current_user_id


def test_dev_auth_resolves_configured_user(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_MODE", "true")
    monkeypatch.setenv("DEV_USER_ID", "user001")
    get_settings.cache_clear()
    try:
        identity = resolve_current_user_id(None)
        assert identity.user_id == "user001"
        assert identity.source == "dev"
    finally:
        get_settings.cache_clear()


def test_non_dev_mode_requires_token():
    with pytest.raises(HTTPException):
        resolve_current_user_id(None)


def test_jwt_sub_still_resolved_in_dev_mode():
    identity = resolve_current_user_id("someone-else")
    assert identity.user_id == "someone-else"
    assert identity.source == "jwt"


def test_dev_auth_rejected_in_production():
    settings = Settings(
        app_env="production",
        dev_auth_mode=True,
        jwt_secret="production-secret-that-is-long-enough-32",
    )
    with pytest.raises(ValueError, match="DEV_AUTH_MODE"):
        settings.validate_runtime()


def test_get_current_user_uses_dev_identity(db, sample_users, monkeypatch):
    """Without a token, a request resolves to DEV_USER_ID instead of 401."""

    from backend.app.auth import get_current_user

    monkeypatch.setenv("DEV_AUTH_MODE", "true")
    monkeypatch.setenv("DEV_USER_ID", "a")
    get_settings.cache_clear()
    try:
        user = get_current_user(credentials=None, db=db)
        assert user.id == "a"
    finally:
        get_settings.cache_clear()


def test_get_current_user_still_401_without_token_or_dev_mode(db):
    from backend.app.auth import get_current_user

    with pytest.raises(HTTPException):
        get_current_user(credentials=None, db=db)


def test_invalid_bearer_never_falls_back_to_dev_user(db, sample_users, monkeypatch):
    from backend.app.auth import get_current_user

    monkeypatch.setenv("DEV_AUTH_MODE", "true")
    monkeypatch.setenv("DEV_USER_ID", "a")
    get_settings.cache_clear()
    try:
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-token"
        )
        with pytest.raises(HTTPException) as error:
            get_current_user(credentials=credentials, db=db)
        assert error.value.status_code == 401
    finally:
        get_settings.cache_clear()
