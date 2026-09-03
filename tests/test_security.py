from datetime import datetime, timedelta, timezone

import pytest

from backend.app.config import Settings
from backend.app.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("SecurePass123!")
    second = hash_password("SecurePass123!")
    assert first != second
    assert verify_password("SecurePass123!", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("SecurePass123!", "malformed")


def test_access_token_requires_valid_signature_and_expiry():
    settings = Settings(jwt_secret="x" * 32, jwt_access_token_minutes=5)
    token = create_access_token("user001", settings=settings)
    payload = decode_access_token(token, settings=settings)
    assert payload["sub"] == "user001"
    assert payload["ver"] == 0
    assert payload["type"] == "access"

    expired = create_access_token(
        "user001",
        settings=settings,
        now=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    with pytest.raises(TokenError):
        decode_access_token(expired, settings=settings)


def test_production_rejects_default_jwt_secret():
    settings = Settings(app_env="production")
    with pytest.raises(ValueError, match="changed in production"):
        settings.validate_runtime()
