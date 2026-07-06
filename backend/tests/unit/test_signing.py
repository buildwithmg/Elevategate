import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from app.core.signing import build_canonical_payload, format_utc_iso


def test_format_utc_iso_uses_z_suffix_and_microsecond_precision():
    dt = datetime(2026, 7, 6, 12, 35, 0, 123000, tzinfo=timezone.utc)
    assert format_utc_iso(dt) == "2026-07-06T12:35:00.123000Z"


def test_format_utc_iso_converts_non_utc_to_utc():
    dt = datetime(2026, 7, 6, 16, 35, 0, 123000, tzinfo=timezone(timedelta(hours=4)))
    assert format_utc_iso(dt) == "2026-07-06T12:35:00.123000Z"


def test_format_utc_iso_rejects_naive_datetime():
    with pytest.raises(ValueError):
        format_utc_iso(datetime(2026, 7, 6, 12, 35, 0))


def test_canonical_payload_is_deterministic():
    issued = datetime(2026, 7, 6, 12, 30, 0, tzinfo=timezone.utc)
    expires = issued + timedelta(minutes=5)
    a = build_canonical_payload(
        request_uuid="req-1", device_uuid="dev-1", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    b = build_canonical_payload(
        request_uuid="req-1", device_uuid="dev-1", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    assert a == b


@pytest.mark.parametrize(
    "override",
    ["request_uuid", "device_uuid", "sha256", "action", "nonce"],
)
def test_canonical_payload_changes_when_any_field_changes(override):
    issued = datetime(2026, 7, 6, 12, 30, 0, tzinfo=timezone.utc)
    expires = issued + timedelta(minutes=5)
    base_kwargs = dict(
        request_uuid="req-1", device_uuid="dev-1", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    baseline = build_canonical_payload(**base_kwargs)

    varied_kwargs = dict(base_kwargs)
    varied_kwargs[override] = varied_kwargs[override] + "-different"
    varied = build_canonical_payload(**varied_kwargs)

    assert baseline != varied


def test_canonical_payload_field_boundaries_cannot_be_shifted():
    # Without length-prefixing, "ab"+"cd" and "a"+"bcd" would concatenate identically.
    issued = datetime(2026, 7, 6, 12, 30, 0, tzinfo=timezone.utc)
    expires = issued + timedelta(minutes=5)
    a = build_canonical_payload(
        request_uuid="ab", device_uuid="cd", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    b = build_canonical_payload(
        request_uuid="a", device_uuid="bcd", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    assert a != b


def test_sign_and_verify_round_trip():
    private_key = Ed25519PrivateKey.generate()
    issued = datetime.now(timezone.utc)
    expires = issued + timedelta(minutes=5)
    payload = build_canonical_payload(
        request_uuid="req-1", device_uuid="dev-1", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )

    signature = private_key.sign(payload)

    # Does not raise => valid.
    private_key.public_key().verify(signature, payload)


def test_tampered_payload_fails_verification():
    private_key = Ed25519PrivateKey.generate()
    issued = datetime.now(timezone.utc)
    expires = issued + timedelta(minutes=5)
    payload = build_canonical_payload(
        request_uuid="req-1", device_uuid="dev-1", sha256="ab" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )
    signature = private_key.sign(payload)

    tampered_payload = build_canonical_payload(
        request_uuid="req-1", device_uuid="dev-1", sha256="cd" * 32,
        action="execute", issued_at=issued, expires_at=expires, nonce="nonce-1",
    )

    with pytest.raises(InvalidSignature):
        private_key.public_key().verify(signature, tampered_payload)


def test_ed25519_cross_library_interop_known_vector():
    """
    This exact (public key, message, signature) triple was empirically produced and verified
    during design of this backend: signed with Python's `cryptography` library, then verified
    successfully against the *actual* .NET agent's Ed25519Verifier (BouncyCastle-backed) in
    ElevateGate.Core. It's re-verified here with Python's own Ed25519PublicKey.verify() as a
    permanent regression guard that Ed25519 signing/verification in this codebase still behaves
    per RFC 8032 (the message bytes here are illustrative, not this backend's actual 7-field
    payload format - see build_canonical_payload for that).
    """
    public_key_b64 = "tBRKExqE9S1JWa18vwBsYlnhIgjmKszgpJK1Y8k1ALY="
    signature_b64 = "wHjbfYbA63Qi8ZO/NHzJQqFKOWh3V44Jhl3jkzjJDMtoBf4WWkVCuqZIdE8VEgOuBf1R9aut2tw9lSzu5mYuDA=="
    message_hex = (
        "01000a6465766963652d616263000b726571756573742d78797a"
        "0040653362306334343239386663316331343961666266346338"
        "3939366662393234323761653431653436343962393334636134"
        "3935393931623738353262383535"
        "0021323032362d30372d30365431323a33353a30302e31323330"
        "3030302b30303a3030"
        "00096e6f6e63652d313233"
    )

    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    signature = base64.b64decode(signature_b64)
    message = bytes.fromhex(message_hex)

    public_key.verify(signature, message)  # does not raise => interop confirmed
