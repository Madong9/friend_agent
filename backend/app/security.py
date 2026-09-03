"""Password hashing and signed access tokens for the authentication boundary."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import Settings, get_settings

PASSWORD_SCHEME = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
JWT_ALGORITHM = "HS256"


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    if not 8 <= len(password) <= 128:
        raise ValueError("password must contain 8 to 128 characters")
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return "$".join(
        [
            PASSWORD_SCHEME,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            salt.hex(),
            derived.hex(),
        ]
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n, r, p, salt_hex, expected_hex = encoded.split("$", 5)
        if scheme != PASSWORD_SCHEME:
            return False
        parameters = (int(n), int(r), int(p))
        if parameters != (SCRYPT_N, SCRYPT_R, SCRYPT_P):
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=parameters[0],
            r=parameters[1],
            p=parameters[2],
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (TypeError, ValueError):
        return False


# Unknown users still perform one scrypt verification to reduce login timing leakage.
DUMMY_PASSWORD_HASH = hash_password("invalid-login-dummy-password")


def create_access_token(
    user_id: str,
    settings: Settings | None = None,
    now: datetime | None = None,
    token_version: int = 0,
) -> str:
    settings = settings or get_settings()
    settings.validate_runtime()
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_minutes)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": issued_at,
            "exp": expires_at,
            "iss": settings.jwt_issuer,
            "type": "access",
            "ver": token_version,
        },
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str, settings: Settings | None = None
) -> dict[str, object]:
    settings = settings or get_settings()
    settings.validate_runtime()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "type"]},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid or expired access token") from exc
    if (
        payload.get("type") != "access"
        or not isinstance(payload.get("sub"), str)
        or not isinstance(payload.get("ver"), int)
    ):
        raise TokenError("invalid access token claims")
    return payload
