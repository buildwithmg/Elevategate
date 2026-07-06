"""
Ed25519 approval signing.

The private key is loaded once, lazily, from a mounted file or a base64 env var — never from the
database, never logged. See docs/BACKEND_THREAT_MODEL.md.
"""

import base64
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings

SCHEMA_VERSION = 1
_MAX_FIELD_BYTES = 0xFFFF


def format_utc_iso(dt: datetime) -> str:
    """Deterministic UTC ISO-8601 string with microsecond precision and a literal 'Z' suffix."""
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _write_field(buffer: bytearray, value: str) -> None:
    encoded = value.encode("utf-8")
    if len(encoded) > _MAX_FIELD_BYTES:
        raise ValueError("Field too long to encode in canonical approval payload.")
    buffer.extend(len(encoded).to_bytes(2, "big"))
    buffer.extend(encoded)


def build_canonical_payload(
    *,
    request_uuid: str,
    device_uuid: str,
    sha256: str,
    action: str,
    issued_at: datetime,
    expires_at: datetime,
    nonce: str,
) -> bytes:
    """
    Builds the exact byte sequence that gets Ed25519-signed for an approval:
    schema_version(1 byte) + 7 length-prefixed (2-byte big-endian) UTF-8 fields, in this order:
    request_uuid, device_uuid, sha256 (lowercase hex text), action, issued_at, expires_at, nonce.

    Length-prefixing (rather than delimiting) means no field's content can ever be crafted to
    shift where one field ends and the next begins. See docs/API_CONTRACT.md.

    NOTE: this is a distinct, incompatible byte layout from the one already implemented in the
    existing .NET agent (ElevateGate.Core.Crypto.CanonicalApprovalPayload has 5 fields - no
    `action`, no `issued_at` - and a different timestamp format). That agent was built against an
    earlier placeholder contract; this backend was specified with an explicit 7-field payload.
    Reconciling the two is a follow-up task on the agent side - see docs/API_CONTRACT.md.
    """
    buffer = bytearray([SCHEMA_VERSION])
    _write_field(buffer, request_uuid)
    _write_field(buffer, device_uuid)
    _write_field(buffer, sha256.lower())
    _write_field(buffer, action)
    _write_field(buffer, format_utc_iso(issued_at))
    _write_field(buffer, format_utc_iso(expires_at))
    _write_field(buffer, nonce)
    return bytes(buffer)


@lru_cache
def _get_private_key() -> Ed25519PrivateKey:
    settings = get_settings()
    if settings.ed25519_private_key_b64:
        raw_b64 = settings.ed25519_private_key_b64.strip()
    elif settings.ed25519_private_key_path:
        raw_b64 = Path(settings.ed25519_private_key_path).read_text().strip()
    else:
        raise RuntimeError(
            "No Ed25519 signing key configured - set ED25519_PRIVATE_KEY_B64 or "
            "ED25519_PRIVATE_KEY_PATH. The key is never read from the database."
        )
    key_bytes = base64.b64decode(raw_b64)
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def sign_payload(payload: bytes) -> bytes:
    return _get_private_key().sign(payload)


def get_public_key_b64() -> str:
    """Operational use only (e.g. confirming which key is loaded at startup) - never served over the API."""
    public_bytes = _get_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(public_bytes).decode("ascii")
