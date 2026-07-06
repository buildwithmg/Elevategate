"""
Password/secret hashing and JWT issuance.

Nothing in this module ever logs the plaintext it's given — callers must be equally careful not
to log passwords, device secrets, or JWTs upstream of these functions. See
docs/BACKEND_THREAT_MODEL.md.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import get_settings

_hasher = PasswordHasher()


def hash_secret(plaintext: str) -> str:
    """Argon2id-hash a password or device secret. Used for both AdminUser.password_hash and Device.device_secret_hash."""
    return _hasher.hash(plaintext)


def verify_secret(plaintext: str, hashed: str) -> bool:
    """Constant-time-verifies plaintext against an Argon2id hash. Never raises — any failure mode is simply "not valid"."""
    try:
        return _hasher.verify(hashed, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_device_secret() -> str:
    """A cryptographically random device enrollment secret, returned to the caller exactly once."""
    return secrets.token_urlsafe(32)


class TokenError(Exception):
    """Raised for any invalid/expired/malformed JWT. Deliberately generic - callers don't need
    (and shouldn't expose) the specific PyJWT exception type to API clients."""


def create_access_token(*, subject: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token.") from exc
