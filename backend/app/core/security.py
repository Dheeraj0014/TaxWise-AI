"""Password hashing + JWT issuing/verifying (§8).

Blueprint uses Argon2id + RS256; this MVP uses bcrypt + HS256 for zero-config
local run. The interface is the same, so the upgrade is a config swap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def _create_token(sub: str, role: str, ttl: timedelta, token_type: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(sub: str, role: str) -> str:
    s = get_settings()
    return _create_token(sub, role, timedelta(minutes=s.access_token_ttl_minutes), "access")


def create_refresh_token(sub: str, role: str) -> str:
    s = get_settings()
    return _create_token(sub, role, timedelta(days=s.refresh_token_ttl_days), "refresh")


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise ValueError(str(exc)) from exc
